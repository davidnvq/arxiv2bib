## Get a BibTeX entry from an arXiv id number

This is a fork from https://github.com/nathangrigg/arxiv2bib with some modification:

- Change the `cli` name from `arxiv2bib` to `a2b`.
- Change the `bibtex` format.
- Be able to get the `cite_name` of the bibtex that is consistent to Google scholar `bibtex`.
- Be able to get the `bibtex` from the full arxiv url.


## Installation

Clone this repo and run
```
python setup.py install
```

## Examples

```
a2b https://arxiv.org/abs/1911.11390

# or the shorter
a2b 1911.11390
```

Call as a module
```python
import arxiv2bib
arxiv_id = "1911.11390"
paper = arxiv2bib.arxiv2bib(id_list=[arxiv_id])[0]
bibtex = paper.bibtex()
cite_name = paper.cite_name
print(cite_name)
print(bibtex)
```