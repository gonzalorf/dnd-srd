LANG ?= es

.PHONY: build extract blocks document collect export validate test clean \
        web web-dev web-preview web-check

build:      ; python -m extractor --lang $(LANG) build
extract:    ; python -m extractor --lang $(LANG) extract
blocks:     ; python -m extractor --lang $(LANG) blocks
document:   ; python -m extractor --lang $(LANG) document
collect:    ; python -m extractor --lang $(LANG) collect
export:     ; python -m extractor --lang $(LANG) export
validate:   ; python -m extractor --lang $(LANG) validate
test:       ; python -m pytest tests -q
web:         ; cd apps/web && npm install && npm run build
web-dev:     ; cd apps/web && npm run dev
web-preview: ; cd apps/web && npm run preview
web-check:   ; cd apps/web && npm run check
clean:       ; rm -rf data/raw data/interim data/processed apps/web/dist
