# Publications YAML Documentation

## Overview

The `publications.yaml` file contains structured data for selected publications with comprehensive auto-generated descriptions. This file can be used for:

- Displaying publication information dynamically on the website
- Generating publication lists programmatically
- Providing detailed context about research contributions
- Supporting multilingual descriptions in the future
- Enabling easy updates and maintenance of publication data

## File Structure

### Main Sections

1. **selected_publications**: Array of publication objects
2. **metadata**: File metadata and generation information

### Publication Object Structure

Each publication in the `selected_publications` array contains:

```yaml
- title: "Paper Title"                    # Full paper title
  authors:                                 # List of authors
    - name: "Author Name"                  # Author name
      highlight: true                      # Optional: Mark as highlighted author
    - "Another Author"                     # Simple string for non-highlighted authors
  venue: "Conference/Journal, Year"        # Publication venue
  paper_url: "https://..."                 # Link to paper (arXiv, DOI, etc.)
  code_url: "https://..."                  # Link to code repository
  image: "assets/img/..."                  # Preview image path
  description: >                           # Multi-line comprehensive description
    Detailed description of the paper's contributions,
    methodology, and impact...
```

## Field Descriptions

### Required Fields

- **title** (string): The full title of the publication
- **authors** (array): List of authors, can be simple strings or objects with `name` and `highlight` fields
- **venue** (string): Publication venue and year
- **description** (string): Comprehensive description of the paper

### Optional Fields

- **paper_url** (string): URL to the paper (arXiv, conference website, etc.)
- **code_url** (string): URL to the code repository (GitHub, etc.)
- **image** (string): Path to preview image
- **highlight** (boolean): For author objects, marks the author as highlighted (typically the main author)

## Description Guidelines

The auto-generated descriptions follow these principles:

1. **Comprehensive Coverage**: Each description is 800-1400 characters, providing thorough context
2. **Technical Accuracy**: Descriptions accurately reflect the paper's technical contributions
3. **Impact Focus**: Highlights the practical and theoretical impact of the work
4. **Accessibility**: Written to be understandable by both experts and educated non-specialists
5. **Context**: Provides background on the problem being solved and why it matters

## Usage Examples

### Python

```python
import yaml

# Load the YAML file
with open('publications.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Access publications
publications = data['selected_publications']

# Iterate through publications
for pub in publications:
    print(f"Title: {pub['title']}")
    print(f"Venue: {pub['venue']}")
    print(f"Description: {pub['description'][:100]}...")
    print()
```

### JavaScript/Node.js

```javascript
const yaml = require('js-yaml');
const fs = require('fs');

// Load the YAML file
const data = yaml.load(fs.readFileSync('publications.yaml', 'utf8'));

// Access publications
const publications = data.selected_publications;

// Display publication titles
publications.forEach(pub => {
    console.log(`${pub.title} (${pub.venue})`);
});
```

### HTML/Jekyll (Static Site Generator)

If using Jekyll or similar static site generators:

1. Place the YAML file in the `_data` directory:
```
_data/publications.yaml
```

2. Access the data in your template:
```html
{% for pub in site.data.publications.selected_publications %}
<div class="publication">
    <h3>{{ pub.title }}</h3>
    <p class="authors">
        {% for author in pub.authors %}
            {% if author.name %}
                {% if author.highlight %}
                    <strong>{{ author.name }}</strong>
                {% else %}
                    {{ author.name }}
                {% endif %}
            {% else %}
                {{ author }}
            {% endif %}
            {% unless forloop.last %}, {% endunless %}
        {% endfor %}
    </p>
    <p class="venue">{{ pub.venue }}</p>
    <p class="description">{{ pub.description }}</p>
    <a href="{{ pub.paper_url }}">Paper</a>
    <a href="{{ pub.code_url }}">Code</a>
</div>
{% endfor %}
```

## Maintenance

### Adding New Publications

To add a new publication:

1. Add a new object to the `selected_publications` array
2. Fill in all required fields
3. Write a comprehensive description following the guidelines above
4. Update the `metadata.total_selected_publications` count
5. Validate the YAML syntax

### Updating Descriptions

Descriptions can be updated or expanded as papers gain citations, win awards, or have broader impact. Keep the style consistent with existing descriptions.

### Validation

Always validate the YAML after making changes:

```bash
# Python
python3 -c "import yaml; yaml.safe_load(open('publications.yaml'))"

# Node.js
node -e "const yaml = require('js-yaml'); const fs = require('fs'); yaml.load(fs.readFileSync('publications.yaml', 'utf8'));"
```

## Metadata Section

The metadata section provides information about the file itself:

```yaml
metadata:
  generated_date: "2025-12-04"                    # Date the file was created/updated
  total_selected_publications: 7                  # Total number of publications
  description_language: "English"                 # Language of descriptions
  description_style: "Comprehensive, technical"   # Description style guide
  note: "Information about auto-generation..."    # Additional notes
```

## Future Enhancements

Possible future additions to this file:

1. **Multilingual Support**: Add description fields for other languages (e.g., `description_cn` for Chinese)
2. **Tags/Keywords**: Add topic tags for filtering and categorization
3. **Citation Metrics**: Include citation counts, h-index, etc.
4. **Bibtex**: Include BibTeX entries for easy citation
5. **Related Papers**: Link to related work
6. **Media Coverage**: Links to blog posts, news articles, etc.

## License

This documentation and the publications.yaml file are part of the anxiangsir.github.io repository. Please refer to the repository's LICENSE file for terms of use.

## Contact

For questions or suggestions about the YAML structure or descriptions, please open an issue in the repository or contact the maintainer.
