# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = Joule
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

#livehtml:
#	sphinx-autobuild --host 0.0.0.0 $(SOURCEDIR) $(BUILDDIR)/html -z ../joule -i *___ -E
livehtml:
	sphinx-autobuild --host 0.0.0.0 "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) --watch ../joule $(O)
deploy: html
	rsync -r --delete $(BUILDDIR)/html/ jdonnal@wattsworth.net:/var/www/docs/joule
	ssh jdonnal@wattsworth.net ./update_doc_tarball.sh
