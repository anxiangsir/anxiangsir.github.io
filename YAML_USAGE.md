# Using YAML for Dynamic Content Generation

This website uses YAML files to dynamically generate publication content. This approach separates content from presentation, making it easy to update publications without modifying HTML files.

## Overview

The system consists of three main components:

1. **YAML Files** (`_data/*.yaml`) - Store publication data
2. **YAML Parser** (`assets/js/yaml-parser.js`) - Parses YAML into JavaScript objects
3. **Publications Loader** (`assets/js/publications-loader.js`) - Generates HTML from parsed data

## YAML Files

### `_data/publications.yaml`

Contains the full list of all publications displayed on `publications.html`.

**Structure:**
```yaml
publications:
  - title: "Paper Title"
    authors: "Author1, Author2, Xiang An, Author3"
    venue: "Conference/Journal Year"
```

### `_data/selected_publications.yaml`

Contains featured publications displayed on the homepage (`index.html`).

**Structure:**
```yaml
publications:
  - title: "Paper Title"
    authors: "Author1, Author2, Xiang An, Author3"
    venue: "Conference, Year"
    paper_url: "https://arxiv.org/abs/..."
    code_url: "https://github.com/..."
    preview_image: "assets/img/publication_preview_N.jpg"
    summary: |
      Multi-line summary of the paper.
      Can span multiple lines.
```

## How to Add a New Publication

### For All Publications List

1. Open `_data/publications.yaml`
2. Add a new entry at the appropriate position:

```yaml
  - title: "Your New Paper Title"
    authors: "Author1, Xiang An, Author2"
    venue: "Conference 2026"
```

3. Commit and push - the website will automatically display the new publication!

### For Selected Publications (Homepage)

1. Open `_data/selected_publications.yaml`
2. Add a new entry with additional metadata:

```yaml
  - title: "Your New Paper Title"
    authors: "Xiang An, Co-author1, Co-author2"
    venue: "Top Conference, 2026"
    paper_url: "https://arxiv.org/abs/xxxx.xxxxx"
    code_url: "https://github.com/username/repo"
    preview_image: "assets/img/publication_preview_X.jpg"
    summary: |
      Brief description of your paper contribution.
      Explain the main idea and impact.
```

3. If you have a preview image, place it in `assets/img/` directory
4. Commit and push

## Features

### Automatic Author Highlighting

The system automatically highlights "Xiang An" in the author list with special styling. It also handles special cases like "Xiang An (Project Leader)".

### External Link Support

For selected publications, the system automatically adds "Paper" and "Code" badges if URLs are provided in the YAML.

### Loading States

While loading YAML data, pages display an animated loading indicator. If loading fails, users see a friendly error message.

### Animation Effects

Publications appear with staggered fade-in animations for a smooth user experience.

## Technical Details

### YAML Parser

The custom YAML parser (`yaml-parser.js`) supports:
- Key-value pairs
- Multi-line values (using `|` syntax)
- Nested structures
- Comments (lines starting with `#` are ignored)

### Error Handling

The loader includes comprehensive error handling:
- Network errors when fetching YAML files
- Parse errors in YAML syntax
- Missing or invalid data structures
- Missing DOM elements

All errors are logged to the console and displayed to users when appropriate.

## Browser Compatibility

The dynamic loading system works in all modern browsers:
- Chrome/Edge 60+
- Firefox 55+
- Safari 11+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Maintenance Notes

### Code Review Suggestions

The code review identified some minor improvements that could be made:

1. **Loading Spinner Duplication**: The loading indicator styles are duplicated in both `index.html` and `publications.html`. These could be extracted to a shared CSS class.

2. **DOM Query Optimization**: The publications loader checks for DOM elements before validating data. Checking data first would be slightly more efficient.

These are non-critical optimizations and don't affect functionality.

### Security

The code has been scanned with CodeQL and no security vulnerabilities were found.

## Examples

### Minimal Publication Entry

```yaml
  - title: "Simple Paper"
    authors: "Xiang An, Collaborator"
    venue: "Conference 2025"
```

### Full Publication Entry with All Fields

```yaml
  - title: "Comprehensive Research Paper"
    authors: "First Author, Xiang An (Project Leader), Third Author"
    venue: "Top Conference, 2025 (Oral)"
    paper_url: "https://arxiv.org/abs/2025.12345"
    code_url: "https://github.com/research/project"
    preview_image: "assets/img/paper_preview.jpg"
    summary: |
      This paper presents groundbreaking research in the field.
      The method achieves state-of-the-art results.
      It has practical applications in real-world scenarios.
```

## Troubleshooting

### Publications Not Appearing

1. Check browser console for errors (F12)
2. Verify YAML syntax is correct (proper indentation, quotes, etc.)
3. Ensure file paths are correct
4. Check that JavaScript files are loading properly

### YAML Syntax Errors

Common mistakes:
- Inconsistent indentation (use 2 spaces per level)
- Missing quotes around titles with special characters
- Incorrect multi-line syntax (use `|` followed by proper indentation)
- Mixing tabs and spaces (use spaces only)

### Testing Locally

To test changes locally:

```bash
# Start a local server
python -m http.server 8000

# Open in browser
http://localhost:8000
```

Check the browser console for any loading errors or success messages.
