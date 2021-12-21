# Scale any PDF document to different paper sizes

Example:

```
./pdfscale.py -f A4 document.pdf
```

will create a new file `document-scaled.pdf` where every page is set to DIN-A4
paper size by enlarging each pages width or height if necessary.

No contents are cut or stretched, so the aspect ratio of the content is always
preserved.
