from __future__ import print_function
from xml.etree import ElementTree
import sys
import re
import os

if sys.version_info < (2, 6):
    raise Exception("Python 2.6 or higher required")

# Python 2 compatibility code
PY2 = sys.version_info[0] == 2
if not PY2:
    from urllib.parse import urlencode
    from urllib.request import urlopen
    from urllib.error import HTTPError
    print_bytes = lambda s: sys.stdout.buffer.write(s)
else:
    from urllib import urlencode
    from urllib2 import HTTPError, urlopen
    print_bytes = lambda s: sys.stdout.write(s)


# Namespaces
ATOM = '{http://www.w3.org/2005/Atom}'
ARXIV = '{http://arxiv.org/schemas/atom}'

# regular expressions to check if arxiv id is valid
NEW_STYLE = re.compile(r'^\d{4}\.\d{4,}(v\d+)?$')
OLD_STYLE = re.compile(r"""(?x)
^(
   math-ph
  |hep-ph
  |nucl-ex
  |nucl-th
  |gr-qc
  |astro-ph
  |hep-lat
  |quant-ph
  |hep-ex
  |hep-th
  |stat
    (\.(AP|CO|ML|ME|TH))?
  |q-bio
    (\.(BM|CB|GN|MN|NC|OT|PE|QM|SC|TO))?
  |cond-mat
    (\.(dis-nn|mes-hall|mtrl-sci|other|soft|stat-mech|str-el|supr-con))?
  |cs
    (\.(AR|AI|CL|CC|CE|CG|GT|CV|CY|CR|DS|DB|DL|DM|DC|GL|GR|HC|IR|IT|LG|LO|
      MS|MA|MM|NI|NE|NA|OS|OH|PF|PL|RO|SE|SD|SC))?
  |nlin
    (\.(AO|CG|CD|SI|PS))?
  |physics
    (\.(acc-ph|ao-ph|atom-ph|atm-clus|bio-ph|chem-ph|class-ph|comp-ph|
      data-an|flu-dyn|gen-ph|geo-ph|hist-ph|ins-det|med-ph|optics|ed-ph|
      soc-ph|plasm-ph|pop-ph|space-ph))?
  |math
      (\.(AG|AT|AP|CT|CA|CO|AC|CV|DG|DS|FA|GM|GN|GT|GR|HO|IT|KT|LO|MP|MG
      |NT|NA|OA|OC|PR|QA|RT|RA|SP|ST|SG))?
)/\d{7}(v\d+)?$""")


def is_valid(arxiv_id):
    """Checks if id resembles a valid arxiv identifier."""
    return bool(NEW_STYLE.match(arxiv_id)) or bool(OLD_STYLE.match(arxiv_id))


class FatalError(Exception):
    """Error that prevents us from continuing"""


class NotFoundError(Exception):
    """Reference not found by the arxiv API"""


class Reference(object):
    """Represents a single reference.

    Instantiate using Reference(entry_xml). Note entry_xml should be
    an ElementTree.Element object.
    """
    def __init__(self, entry_xml):
        self.xml = entry_xml
        self.url = self._field_text('id')
        self.id = self._id()
        self.authors = self._authors()
        self.title = self._field_text('title')
        if len(self.id) == 0 or len(self.authors) == 0 or len(self.title) == 0:
            raise NotFoundError("No such publication", self.id)
        self.summary = self._field_text('summary')
        self.category = self._category()
        self.year, self.month = self._published()
        self.updated = self._field_text('updated')
        self.bare_id = self.id[:self.id.rfind('v')]
        self.note = self._field_text('journal_ref', namespace=ARXIV)
        self.doi = self._field_text('doi', namespace=ARXIV)
        self.cite_name = ''

    def _authors(self):
        """Extracts author names from xml."""
        xml_list = self.xml.findall(ATOM + 'author/' + ATOM + 'name')
        return [field.text for field in xml_list]

    def _field_text(self, id, namespace=ATOM):
        """Extracts text from arbitrary xml field"""
        try:
            return self.xml.find(namespace + id).text.strip()
        except:
            return ""

    def _category(self):
        """Get category"""
        try:
            return self.xml.find(ARXIV + 'primary_category').attrib['term']
        except:
            return ""

    def _id(self):
        """Get arxiv id"""
        try:
            id_url = self._field_text('id')
            return id_url[id_url.find('/abs/') + 5:]
        except:
            return ""

    def _published(self):
        """Get published date"""
        published = self._field_text('published')
        if len(published) < 7:
            return "", ""
        y, m = published[:4], published[5:7]
        try:
            m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                 "Aug", "Sep", "Oct", "Nov", "Dec"][int(m) - 1]
        except:
            pass
        return y, m

    def bibtex(self):
        """BibTex string of the reference."""

        cite_name = self.authors[0].split(' ')[-1]
        cite_name += str(self.year)
        cite_name += self.title.split(' ')[0]
        cite_name = cite_name.replace(":", "")
        self.cite_name = cite_name
        lines = ["@article{" + cite_name]

        for k, v in [("author", " and ".join(self.authors)),
                    ("title", self.title),
                    # ("Eprint", self.id),
                    # ("DOI", self.doi),
                    # ("ArchivePrefix", "arXiv"),
                    # ("PrimaryClass", self.category),
                    # ("abstract", self.summary),
                    ("journal", f"arXiv preprint arXiv:{self.id}"),
                    ("year", self.year),
                    ("month", self.month),
                    ("note", self.note),
                    ("url", self.url),
                    ("file", self.id + ".pdf"),
                    ]:
            if len(v):
                lines.append("%-13s = {%s}" % (k, v))
        cite_bib = ("," + os.linesep).join(lines) + os.linesep + "}"
        
        return cite_bib


class ReferenceErrorInfo(object):
    """Contains information about a reference error"""
    def __init__(self, message, id):
        self.message = message
        self.id = id
        self.bare_id = id[:id.rfind('v')]
        # mark it as really old, so it gets superseded if possible
        self.updated = '0'

    def bibtex(self):
        """BibTeX comment explaining error"""
        return "@comment{%(id)s: %(message)s}" % \
                {'id': self.id, 'message': self.message}

    def __str__(self):
        return "Error: %(message)s (%(id)s)" % \
                {'id': self.id, 'message': self.message}

def arxiv2bib(id_list):
    """Returns a list of references, corresponding to elts of id_list"""
    d = arxiv2bib_dict(id_list)
    l = []
    for id in id_list:
        try:
            l.append(d[id])
        except:
            l.append(ReferenceErrorInfo("Not found", id))

    return l

def arxiv_request(ids):
    """Sends a request to the arxiv API."""
    q = urlencode([
         ("id_list", ",".join(ids)),
         ("max_results", len(ids))
         ])
    xml = urlopen("http://export.arxiv.org/api/query?" + q)
    # xml.read() returns bytes, but ElementTree.fromstring decodes
    # to unicode when needed (python2) or string (python3)
    return ElementTree.fromstring(xml.read())

def arxiv2bib_dict(id_list):
    """Fetches citations for ids in id_list into a dictionary indexed by id"""
    ids = []
    d = {}

    # validate ids
    for id in id_list:
        if is_valid(id):
            ids.append(id)
        else:
            d[id] = ReferenceErrorInfo("Invalid arXiv identifier", id)

    if len(ids) == 0:
        return d

    # make the api call
    while True:
        xml = arxiv_request(ids)

        # check for error
        entries = xml.findall(ATOM + "entry")
        try:
            first_title = entries[0].find(ATOM + "title")
        except:
            raise FatalError("Unable to connect to arXiv.org API.")

        if first_title is None or first_title.text.strip() != "Error":
            break

        try:
            id = entries[0].find(ATOM + "summary").text.split()[-1]
            del(ids[ids.index(id)])
        except:
            raise FatalError("Unable to parse an error returned by arXiv.org.")

    # Parse each reference and store it in dictionary
    for entry in entries:
        try:
            ref = Reference(entry)
        except NotFoundError as error:
            message, id = error.args
            ref = ReferenceErrorInfo(message, id)
        if ref.id:
            d[ref.id] = ref
        if ref.bare_id:
            if not (ref.bare_id in d) or d[ref.bare_id].updated < ref.updated:
                d[ref.bare_id] = ref

    return d

def get_arxiv_id(text):
    """
    text = http://arxiv.org/abs/2005.00743v1
    return = 2005.00743
    """
    format_id = re.compile('[\\d]+.[\\d]+')
    return format_id.findall(text)[0]

class Cli(object):
    """Command line interface"""

    def __init__(self, args=None):
        """Parse arguments"""
        self.args = self.parse_args(args)

        if len(self.args.id) == 0:
            self.args.id = [line.strip() for line in sys.stdin]

        self.args.id = [get_arxiv_id(line) for line in self.args.id]
        #print("arxiv_id", self.args.id)

            
        # avoid duplicate error messages unless verbose is set
        if self.args.comments and not self.args.verbose:
            self.args.quiet = True

        self.output = []
        self.messages = []
        self.error_count = 0
        self.code = 0

    def run(self):
        """Produce output and error messages"""
        try:
            bib = arxiv2bib(self.args.id)
        except HTTPError as error:
            if error.getcode() == 403:
                raise FatalError("""\
    403 Forbidden error. This usually happens when you make many
    rapid fire requests in a row. If you continue to do this, arXiv.org may
    interpret your requests as a denial of service attack.

    For more information, see http://arxiv.org/help/robots.
    """)
            else:
                raise FatalError(
                  "HTTP Connection Error: {0}".format(error.getcode()))

        self.create_output(bib)
        self.code = self.tally_errors(bib)

    def create_output(self, bib):
        """Format the output and error messages"""
        for b in bib:
            if isinstance(b, ReferenceErrorInfo):
                self.error_count += 1
                if self.args.comments:
                    self.output.append(b.bibtex())
                if not self.args.quiet:
                    self.messages.append(str(b))
            else:
                self.output.append(b.bibtex())

    def print_output(self):
        if not self.output:
            return
        
        output_string = os.linesep.join(self.output)
        try:
            print(output_string)
        except UnicodeEncodeError:
            print_bytes((output_string + os.linesep).encode('utf-8'))
            if self.args.verbose:
                self.messages.append(
                  'Could not use system encoding; using utf-8')

    def tally_errors(self, bib):
        """calculate error code"""
        if self.error_count == len(self.args.id):
            self.messages.append("No successful matches")
            return 2
        elif self.error_count > 0:
            self.messages.append("%s of %s matched succesfully" %
              (len(bib) - self.error_count, len(bib)))
            return 1
        else:
            return 0

    def print_messages(self):
        """print messages to stderr"""
        if self.messages:
            self.messages.append("")
            sys.stderr.write(os.linesep.join(self.messages))

    @staticmethod
    def parse_args(args):
        try:
            import argparse
        except:
            sys.exit("Cannot load required module 'argparse'")

        parser = argparse.ArgumentParser(
          description="Get the BibTeX for each arXiv id.",
          epilog="""\
    Returns 0 on success, 1 on partial failure, 2 on total failure.
    Valid BibTeX is written to stdout, error messages to stderr.
    If no arguments are given, ids are read from stdin, one per line.""",
          formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument('id', metavar='arxiv_id', nargs="*",
          help="arxiv identifier, such as 1201.1213")
        parser.add_argument('-c', '--comments', action='store_true',
          help="Include @comment fields with error details")
        parser.add_argument('-q', '--quiet', action='store_true',
          help="Display fewer error messages")
        parser.add_argument('-v', '--verbose', action="store_true",
          help="Display more error messages")
        return parser.parse_args(args)

def main(args=None):
    """Run the command line interface"""
    cli = Cli(args)
    try:
        cli.run()
    except FatalError as err:
        sys.stderr.write(err.args[0] + os.linesep)
        return 2

    cli.print_output()
    cli.print_messages()
    return cli.code

if __name__ == "__main__":
    sys.exit(main())
