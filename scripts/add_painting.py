#!/usr/bin/env python3
"""
Add a new painting (or collection), or append more photos to an existing one.

Usage:
  # New painting
  python3 scripts/add_painting.py "Title" photo1.jpg photo2.jpg ... [options]

  # More photos of an existing painting/collection
  python3 scripts/add_painting.py --append-to "Existing Title" photo3.jpg photo4.jpg

What it does (new-painting mode):
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

What it does (--append-to mode):
  Resizes the given photos the same way and adds them to the matching
  entry's `images:` list in docs/_data/paintings.yml or collections.yml.
  Does not touch the existing stub/analysis text.

It does NOT commit or push anything -- review the result, fill in any
[NEEDS ARTIST INPUT] sections, then commit yourself.

Options:
  --artist "Name"       Artist credit (default: ei9h7)
  --hero FILENAME        Which input file's basename to use as the hero /
                          thumbnail image (default: the first one given).
                          Ignored in --append-to mode (hero is unchanged).
  --collection            Add as a new section in docs/paintings/collections.md
                          and docs/_data/collections.yml instead of a
                          standalone painting page.
  --append-to "Title"     Add photos to an existing painting or collection
                          instead of creating a new one. Matches by title
                          against paintings.yml first, then collections.yml.
  --notes "text"          Free text to seed into the stub's Overview section
                          instead of leaving it as [NEEDS ARTIST INPUT].
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

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO_ROOT, "docs")
IMAGES_DIR = os.path.join(DOCS, "assets", "images")
THUMBS_DIR = os.path.join(DOCS, "assets", "thumbs")
PAINTINGS_DIR = os.path.join(DOCS, "paintings")
PAINTINGS_YML = os.path.join(DOCS, "_data", "paintings.yml")
COLLECTIONS_YML = os.path.join(DOCS, "_data", "collections.yml")
COLLECTIONS_MD = os.path.join(PAINTINGS_DIR, "collections.md")
README = os.path.join(REPO_ROOT, "README.md")
ISSUE_TEMPLATE = os.path.join(REPO_ROOT, ".github", "ISSUE_TEMPLATE", "add-photos.yml")

FULL_MAX = 2000
THUMB_MAX = 600


def slugify(title):
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "untitled"


def load_yaml(path):
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        return yaml.safe_load(f) or []


def dump_yaml(path, data):
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


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


def process_photos(photos, force):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(THUMBS_DIR, exist_ok=True)
    used = set(os.listdir(IMAGES_DIR)) if not force else set()
    dest_names = [dest_basename_for(p, used) for p in photos]

    total_before = total_after = 0
    for src, dest in zip(photos, dest_names):
        before = os.path.getsize(src)
        full_size, thumb_size = process_image(src, dest)
        total_before += before
        total_after += full_size + thumb_size
        print(f"  {os.path.basename(src)} -> {dest}  ({before/1024:.0f}KB -> {full_size/1024:.0f}KB + {thumb_size/1024:.0f}KB thumb)")
    print(f"Total: {total_before/1024/1024:.1f}MB -> {total_after/1024/1024:.1f}MB")
    return dest_names


PAINTING_TEMPLATE = """---
layout: painting
title: {title}
image: {hero}
artist: {artist}
---

## Overview
{overview}

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
{overview}

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


def sync_issue_template(title, is_collection):
    if not os.path.isfile(ISSUE_TEMPLATE):
        return
    with open(ISSUE_TEMPLATE) as f:
        content = f.read()
    label = title + (" (collection)" if is_collection else "")
    option_line = f'        - "{label}"'
    if option_line in content:
        return
    anchor = '        - "🆕 New painting"\n'
    if anchor not in content:
        return
    content = content.replace(anchor, anchor + option_line + "\n", 1)
    with open(ISSUE_TEMPLATE, "w") as f:
        f.write(content)
    print(f"Added '{label}' to the issue-template dropdown ({os.path.relpath(ISSUE_TEMPLATE, REPO_ROOT)})")


def add_new(args, dest_names):
    slug = slugify(args.title)
    hero = dest_names[0]
    if args.hero:
        matches = [d for d in dest_names if d == args.hero or d.startswith(os.path.splitext(args.hero)[0])]
        if matches:
            hero = matches[0]

    today = date.today().strftime("%B %d, %Y")
    overview = args.notes.strip() if args.notes else "[NEEDS ARTIST INPUT: What is this piece, and what prompted it?]"

    if args.collection:
        page = f"paintings/collections.html#{slug}"
        if not os.path.isfile(COLLECTIONS_MD):
            sys.exit(f"{COLLECTIONS_MD} not found")
        with open(COLLECTIONS_MD) as f:
            content = f.read()
        if f"## {args.title}" in content and not args.force:
            sys.exit(f"'{args.title}' already appears in collections.md (use --force to add anyway)")

        section = COLLECTION_SECTION_TEMPLATE.format(
            title=args.title, artist=args.artist, photo_count=len(dest_names), overview=overview
        )
        marker = "## Questions for Artist"
        if marker in content:
            content = content.replace(marker, section + marker, 1)
        else:
            content = content.rstrip() + "\n\n---\n\n" + section
        with open(COLLECTIONS_MD, "w") as f:
            f.write(content)
        print(f"Added section '## {args.title}' to {os.path.relpath(COLLECTIONS_MD, REPO_ROOT)}")

        data = load_yaml(COLLECTIONS_YML)
        data.append({"title": args.title, "image": hero, "page": page, "artist": args.artist, "images": dest_names})
        dump_yaml(COLLECTIONS_YML, data)
        print(f"Registered in {os.path.relpath(COLLECTIONS_YML, REPO_ROOT)}")
    else:
        page = f"paintings/{slug}.html"
        stub_path = os.path.join(PAINTINGS_DIR, f"{slug}.md")
        if os.path.isfile(stub_path) and not args.force:
            sys.exit(f"{stub_path} already exists (use --force to overwrite)")

        stub = PAINTING_TEMPLATE.format(
            title=args.title, hero=hero, artist=args.artist,
            photo_count=len(dest_names), date=today, overview=overview,
        )
        with open(stub_path, "w") as f:
            f.write(stub)
        print(f"Created {os.path.relpath(stub_path, REPO_ROOT)}")

        data = load_yaml(PAINTINGS_YML)
        data.append({"title": args.title, "image": hero, "page": page, "artist": args.artist, "images": dest_names})
        dump_yaml(PAINTINGS_YML, data)
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

    sync_issue_template(args.title, args.collection)

    print()
    print("Next steps:")
    print("  1. Fill in the [NEEDS ARTIST INPUT] sections in the stub")
    print("  2. Build locally to check it: jekyll build --source docs --destination /tmp/_site_check")
    print(f"  3. git add -A && git commit -m 'Add {args.title}'")


def add_append(args, dest_names):
    for yml_path, label in ((PAINTINGS_YML, "painting"), (COLLECTIONS_YML, "collection")):
        data = load_yaml(yml_path)
        for entry in data:
            if entry.get("title", "").strip().lower() == args.append_to.strip().lower():
                entry.setdefault("images", [])
                entry["images"].extend(dest_names)
                dump_yaml(yml_path, data)
                print(f"Added {len(dest_names)} photo(s) to '{entry['title']}' ({label}) in {os.path.relpath(yml_path, REPO_ROOT)}")
                print()
                print("Next steps:")
                print(f"  1. Check docs/paintings/*.md for '{entry['title']}' -- update commentary if these photos change anything")
                print("  2. Build locally to check it: jekyll build --source docs --destination /tmp/_site_check")
                title = entry["title"]
                print(f"  3. git add -A && git commit -m 'Add photos to {title}'")
                return
    sys.exit(f"No existing painting or collection titled '{args.append_to}' found in paintings.yml or collections.yml")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("title", nargs="?", help="Title for a new painting/collection (omit when using --append-to)")
    parser.add_argument("photos", nargs="+")
    parser.add_argument("--artist", default="ei9h7")
    parser.add_argument("--hero")
    parser.add_argument("--collection", action="store_true")
    parser.add_argument("--append-to")
    parser.add_argument("--notes", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.append_to and args.title:
        args.photos = [args.title] + args.photos
        args.title = None
    if not args.append_to and not args.title:
        sys.exit("A title is required unless using --append-to")

    for p in args.photos:
        if not os.path.isfile(p):
            sys.exit(f"Not a file: {p}")

    label = args.append_to or args.title
    print(f"Processing {len(args.photos)} photo(s) for '{label}'...")
    dest_names = process_photos(args.photos, args.force)

    if args.append_to:
        add_append(args, dest_names)
    else:
        add_new(args, dest_names)


if __name__ == "__main__":
    main()
