#!/usr/bin/env python3
"""
Add a new painting (or collection) to the gallery site from a set of photos.

Usage:
  python3 scripts/add_painting.py "Title" photo1.jpg photo2.jpg ... [options]

What it does:
  1. Resizes + re-encodes every photo into docs/assets/images/ (full, 2000px)
     and docs/assets/thumbs/ (grid thumbnail, 600px), matching the site's
     existing compression convention.
  2. Generates a stub docs/paintings/<slug>.md page with front matter and a
     commentary template, its blanks marked [NEEDS ARTIST INPUT: ...].
  3. Registers the new entry in docs/_data/paintings.yml (or
     docs/_data/collections.yml with --collection), including the full
     photo list, so the homepage gallery and detail-page photo grid pick
     it up automatically.
  4. Appends a row to the README table.

It does NOT commit or push anything -- review the generated stub, fill in
the [NEEDS ARTIST INPUT] sections, then commit yourself.

Options:
  --artist "Name"       Artist credit (default: ei9h7)
  --hero FILENAME        Which input file's basename to use as the hero /
                          thumbnail image (default: the first one given)
  --collection            Add as a new section in docs/paintings/collections.md
                          and docs/_data/collections.yml instead of a
                          standalone painting page.
  --force                 Overwrite an existing stub / data entry with the
                          same slug.
"""
import argparse
import os
import re
import sys
from datetime import date

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is required: pip install pillow")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO_ROOT, "docs")
IMAGES_DIR = os.path.join(DOCS, "assets", "images")
THUMBS_DIR = os.path.join(DOCS, "assets", "thumbs")
PAINTINGS_DIR = os.path.join(DOCS, "paintings")
PAINTINGS_YML = os.path.join(DOCS, "_data", "paintings.yml")
COLLECTIONS_YML = os.path.join(DOCS, "_data", "collections.yml")
COLLECTIONS_MD = os.path.join(PAINTINGS_DIR, "collections.md")
README = os.path.join(REPO_ROOT, "README.md")

FULL_MAX = 2000
THUMB_MAX = 600


def slugify(title):
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "untitled"


def process_image(src_path, dest_basename):
    im = Image.open(src_path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "P"):
        im = im.convert("RGB")

    full = im.copy()
    full.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)
    full_path = os.path.join(IMAGES_DIR, dest_basename)
    full.save(full_path, "JPEG", quality=85, optimize=True)

    thumb = im.copy()
    thumb.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    thumb_path = os.path.join(THUMBS_DIR, dest_basename)
    thumb.save(thumb_path, "JPEG", quality=78, optimize=True)

    return os.path.getsize(full_path), os.path.getsize(thumb_path)


def dest_basename_for(src_path, used):
    stem = os.path.splitext(os.path.basename(src_path))[0]
    base = stem + ".jpg"
    n = 2
    while base in used:
        base = f"{stem}-{n}.jpg"
        n += 1
    used.add(base)
    return base


PAINTING_TEMPLATE = """---
layout: painting
title: {title}
image: {hero}
artist: {artist}
---

## Overview
[NEEDS ARTIST INPUT: What is this piece, and what prompted it?]

## Technical Details

**Medium:** [NEEDS ARTIST INPUT]
**Surface/Ground:** [NEEDS ARTIST INPUT]
**Dimensions:** [NEEDS ARTIST INPUT]
**Artist(s):** {artist}

## Visual Analysis (Unbiased Observation)

- {photo_count} photographs documenting the work
[NEEDS ARTIST INPUT: anything the photos alone don't capture -- scale, texture, lighting conditions?]

## Artistic Analysis

[NEEDS ARTIST INPUT:
- What is the primary visual subject or focus?
- Abstract or representational?
- Color palette and tonal range?
- Dominant compositional structure?]

## Conceptual Notes

[NEEDS ARTIST INPUT:
- What does the title mean or reference?
- What inspired this piece?
- How does it relate to other works in the collection?]

## Related Works

[NEEDS ARTIST INPUT: any related pieces?]

---

**Artist:** {artist}
**Thumbnail:** {hero}

**Last Updated:** {date}
"""

COLLECTION_SECTION_TEMPLATE = """## {title}

{{% assign entry = site.data.collections | where: "title", "{title}" | first %}}
<div class="photo-grid">
  {{% for img in entry.images %}}
  <a href="{{{{ "/assets/images/" | append: img | relative_url }}}}" target="_blank" rel="noopener">
    <img src="{{{{ "/assets/thumbs/" | append: img | relative_url }}}}" alt="{title} — documentation photo" loading="lazy">
  </a>
  {{% endfor %}}
</div>

### Overview
[NEEDS ARTIST INPUT: What is this collection, and what prompted it?]

### Technical Details

**Medium:** [NEEDS ARTIST INPUT]
**Number of Pieces:** {photo_count} documented pieces
**Artist(s):** {artist}

### Conceptual Notes

[NEEDS ARTIST INPUT:
- Why present these as a collection rather than individually?
- What connects the pieces?]

---

"""


def yaml_escape(s):
    if any(c in s for c in ':#{}[]&*!|>\'"%@`') or s != s.strip():
        return '"' + s.replace('"', '\\"') + '"'
    return s


def append_yaml_entry(yml_path, title, hero, page, artist, images):
    lines = [f'- title: {yaml_escape(title)}\n']
    lines.append(f'  image: {hero}\n')
    lines.append(f'  page: {page}\n')
    lines.append(f'  artist: {yaml_escape(artist)}\n')
    lines.append('  images:\n')
    for img in images:
        lines.append(f'    - {img}\n')

    with open(yml_path, "a") as f:
        f.writelines(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("title")
    parser.add_argument("photos", nargs="+")
    parser.add_argument("--artist", default="ei9h7")
    parser.add_argument("--hero")
    parser.add_argument("--collection", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    for p in args.photos:
        if not os.path.isfile(p):
            sys.exit(f"Not a file: {p}")

    slug = slugify(args.title)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(THUMBS_DIR, exist_ok=True)

    used = set(os.listdir(IMAGES_DIR)) if not args.force else set()
    dest_names = []
    for p in args.photos:
        dest_names.append(dest_basename_for(p, used))

    hero = dest_names[0]
    if args.hero:
        matches = [d for d in dest_names if d == args.hero or d.startswith(os.path.splitext(args.hero)[0])]
        if matches:
            hero = matches[0]

    print(f"Processing {len(args.photos)} photo(s) for '{args.title}'...")
    total_before = total_after = 0
    for src, dest in zip(args.photos, dest_names):
        before = os.path.getsize(src)
        full_size, thumb_size = process_image(src, dest)
        total_before += before
        total_after += full_size + thumb_size
        print(f"  {os.path.basename(src)} -> {dest}  ({before/1024:.0f}KB -> {full_size/1024:.0f}KB + {thumb_size/1024:.0f}KB thumb)")
    print(f"Total: {total_before/1024/1024:.1f}MB -> {total_after/1024/1024:.1f}MB")

    today = date.today().strftime("%B %d, %Y")

    if args.collection:
        page = f"paintings/collections.html#{slug}"
        if not os.path.isfile(COLLECTIONS_MD):
            sys.exit(f"{COLLECTIONS_MD} not found")
        with open(COLLECTIONS_MD) as f:
            content = f.read()
        if f"## {args.title}" in content and not args.force:
            sys.exit(f"'{args.title}' already appears in collections.md (use --force to add anyway)")

        section = COLLECTION_SECTION_TEMPLATE.format(
            title=args.title, artist=args.artist, photo_count=len(dest_names)
        )
        marker = "## Questions for Artist"
        if marker in content:
            content = content.replace(marker, section + marker, 1)
        else:
            content = content.rstrip() + "\n\n---\n\n" + section
        with open(COLLECTIONS_MD, "w") as f:
            f.write(content)
        print(f"Added section '## {args.title}' to {os.path.relpath(COLLECTIONS_MD, REPO_ROOT)}")

        append_yaml_entry(COLLECTIONS_YML, args.title, hero, page, args.artist, dest_names)
        print(f"Registered in {os.path.relpath(COLLECTIONS_YML, REPO_ROOT)}")
    else:
        page = f"paintings/{slug}.html"
        stub_path = os.path.join(PAINTINGS_DIR, f"{slug}.md")
        if os.path.isfile(stub_path) and not args.force:
            sys.exit(f"{stub_path} already exists (use --force to overwrite)")

        stub = PAINTING_TEMPLATE.format(
            title=args.title, hero=hero, artist=args.artist,
            photo_count=len(dest_names), date=today,
        )
        with open(stub_path, "w") as f:
            f.write(stub)
        print(f"Created {os.path.relpath(stub_path, REPO_ROOT)}")

        append_yaml_entry(PAINTINGS_YML, args.title, hero, page, args.artist, dest_names)
        print(f"Registered in {os.path.relpath(PAINTINGS_YML, REPO_ROOT)}")

        readme_row = (
            f"| ? | ![{args.title}](docs/assets/thumbs/{hero}) | "
            f"[{args.title}](docs/paintings/{slug}.md) | {args.artist} | "
            f"[View](https://ei9h7.github.io/paintings/{page}) |\n"
        )
        if os.path.isfile(README):
            with open(README) as f:
                readme = f.read()
            table_marker = "## 🖼️ Collections"
            if "| # | Thumbnail | Title | Artist(s) | View |" in readme and table_marker in readme:
                idx = readme.index(table_marker)
                readme = readme[:idx].rstrip("\n") + "\n" + readme_row + "\n" + readme[idx:]
                with open(README, "w") as f:
                    f.write(readme)
                print("Appended a row to README.md (fix the '?' index and re-check column alignment)")
            else:
                print("Could not find the README table to append to -- add the row manually:")
                print(readme_row)

    print()
    print("Next steps:")
    print(f"  1. Fill in the [NEEDS ARTIST INPUT] sections in the stub")
    print(f"  2. Build locally to check it: jekyll build --source docs --destination /tmp/_site_check")
    print(f"  3. git add -A && git commit -m 'Add {args.title}'")


if __name__ == "__main__":
    main()
