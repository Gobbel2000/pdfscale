#!/usr/bin/env python3

import argparse
from copy import copy
from decimal import Decimal, InvalidOperation

from pikepdf import (Pdf, Page, PdfMatrix, Operator,
                     parse_content_stream, unparse_content_stream)


# For converting from Inch to mm
INCH = Decimal('25.4')

# 1 User Space Unit or PT in mm (1/72 inch \approx 0.35mm)
PT = Decimal(1)/72 * INCH


def scale(fpath, fmt_mm):
    with Pdf.open(fpath) as pdf:
        scaled_count = 0
        for p in pdf.pages:
            page = Page(p)
            user_unit = Decimal(p.get("/UserUnit", 1))
            fmt = tuple(Decimal(e)/(PT*user_unit) for e in fmt_mm)
            # Avoid this Array getting mutated when setting page.mediabox
            old_mediabox = copy(page.mediabox)

            # diff < 0 => File too small    diff > 0 => File too large
            width = old_mediabox[2] - old_mediabox[0]
            height = old_mediabox[3] - old_mediabox[1]
            x_diff = width - fmt[0]
            y_diff = height - fmt[1]

            # Check if the difference is less than 1 PT
            threshold = 1
            if (abs(x_diff) < threshold and abs(y_diff) < threshold):
                continue

            # Resize top right corner
            # This keeps the bottom left corner at (0, 0) if it is that way
            page.mediabox = [old_mediabox[0],
                             old_mediabox[1],
                             old_mediabox[2] - x_diff,
                             old_mediabox[3] - y_diff]

            # Adjust all other boxes that exist
            for box in ("/CropBox", "/BleedBox", "/TrimBox", "/ArtBox"):
                if p.get(box):
                    p[box] = page.mediabox

            # The width was shrunk most/grown less => Match new width
            if (x_diff > y_diff):
                scale = fmt[0] / width
                # Wanted position  -  Current position
                translation = (page.mediabox[0]
                                   - old_mediabox[0] * scale,
                               page.mediabox[1] + (fmt[1] - height*scale)/2
                                   - old_mediabox[1] * scale)
            # The height was shrunk most/grown less => Match new height
            else:
                scale = fmt[1] / height
                translation = (page.mediabox[0] + (fmt[0] - width*scale)/2
                                   - old_mediabox[0] * scale,
                               page.mediabox[1]
                                   - old_mediabox[1] * scale)

            transform = PdfMatrix().scaled(scale, scale).translated(*translation)

            content_stream = parse_content_stream(p)
            content_stream.insert(0, (transform.shorthand, Operator("cm")))
            new_stream = unparse_content_stream(content_stream)
            p.Contents = pdf.make_stream(new_stream)

            scaled_count += 1

        if scaled_count:
            print(f"Scaled ({scaled_count}/{len(pdf.pages)}) pages")
            pdf.save(fpath[:-4] + "-scaled.pdf")
        else:  # No pages were scaled
            print("File already respects wanted format, nothing to do")


_ISO216_VALUES = {"a": Decimal(1)/4,
                  "b": Decimal(1)/2,
                  "c": Decimal(3)/8}
def iso216_format(series, size):
    """Return a format tuple for an ISO 216 format
    series must be "a", "b" or "c" and size should be an integer with
    0 <= size <= 10.
    """
    height = Decimal(2) ** (_ISO216_VALUES[series] - size/Decimal(2)) * 1000
    width = Decimal(2) ** (_ISO216_VALUES[series] - (size + 1)/Decimal(2)) * 1000
    return width, height


FORMATS = {
    "us letter": (Decimal('8.5') * INCH, 14*INCH),
}

# Abbreviations or alternative names for the entries in FORMATS
SYNONYMS = {
    "letter": "us letter",
}


def get_format(fmt_string):
    """Return the format tuple for the format described by fmt_string
    The return value is in form (width, height) where both values
    are in mm and are either integers or Decimals.
    """
    # Match everything case-insensitively
    fmt_string = fmt_string.lower()
    fmt_string = fmt_string.strip()

    if 'x' in fmt_string:
        try:
            width, height = fmt_string.split('x', 1)
            width = Decimal(width)
            height = Decimal(height)
        except InvalidOperation:
            pass
        else:
            return width, height

    for prefix in ("din-", "din", "iso 216", "iso216", ""):
        if fmt_string.startswith(prefix):
            iso_str = fmt_string[len(prefix):].lstrip()
            try:
                series = iso_str[0]
                size = int(iso_str[1:])
            except (IndexError, ValueError):
                continue
            
            if (series in "abc" and 0 <= size <= 10
                and (fmt := iso216_format(series, size))):
                return fmt
    
    if fmt_string in FORMATS:
        return FORMATS[fmt_string]
    if fmt_string in SYNONYMS:
        return FORMATS[SYNONYMS[fmt_string]]


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("-f", "--format", default="A4")
    parser.add_argument("file",
        help="Path to file to be scaled")

    return parser.parse_args()


def main():
    arguments = parse_arguments()
    page_format = get_format(arguments.format)
    if not page_format:
        print(f"Unrecognized format {arguments.format}")
        exit(1)
    scale(arguments.file, page_format)



if __name__ == "__main__":
    main()
