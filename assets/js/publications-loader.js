/**
 * Publications Loader - Loads publications from YAML files and renders them
 * Updated for Wikipedia-style layout
 */

// Load YAML data from file
async function loadYAML(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const text = await response.text();
        return parseYAML(text);
    } catch (error) {
        console.error('Error loading YAML from', url, ':', error);
        return null;
    }
}

// Highlight the author name (Xiang An)
function highlightAuthor(authorsText) {
    // Handle "Xiang An (Project Leader)" case
    return authorsText.replace(
        /Xiang An(\s*\(Project Leader\))?/g, 
        '<span class="me-highlight">Xiang An$1</span>'
    );
}

// Render link elements for media_links and extra_code_urls
function renderExtraLinks(container, pub) {
    if (pub.extra_code_urls && Array.isArray(pub.extra_code_urls)) {
        pub.extra_code_urls.forEach(item => {
            container.appendChild(document.createTextNode(' '));
            const link = document.createElement('a');
            link.href = item.url;
            link.textContent = '[' + item.name + ']';
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            container.appendChild(link);
        });
    }
    if (pub.media_links && Array.isArray(pub.media_links)) {
        pub.media_links.forEach(item => {
            container.appendChild(document.createTextNode(' '));
            const link = document.createElement('a');
            link.href = item.url;
            link.textContent = '[' + item.name + ']';
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.className = 'media-link';
            container.appendChild(link);
        });
    }
}

// Render selected publications for index.html (Wikipedia style)
async function loadSelectedPublications() {
    // Load both files: selected_publications.yaml (titles only) and publications.yaml (full data)
    const [selectedData, allData] = await Promise.all([
        loadYAML('_data/selected_publications.yaml'),
        loadYAML('_data/publications.yaml')
    ]);
    
    // Try Wikipedia-style selector first, then fallback to old style
    let pubList = document.querySelector('#pub-list');
    if (!pubList) {
        pubList = document.querySelector('#publications + .pub-list');
    }
    if (!pubList) {
        pubList = document.querySelector('.wiki-pub-list');
    }
    
    if (!pubList) {
        console.error('Publications list element not found');
        return;
    }

    if (!selectedData || !selectedData.selected_publications || !allData || !allData.publications) {
        console.error('Failed to load publications data');
        pubList.innerHTML = `
            <li style="color: #ba0000;">
                Failed to load publications. Please check the console for details.
            </li>
        `;
        return;
    }

    // Create a map of publications by title for fast lookup
    const publicationsMap = new Map();
    allData.publications.forEach(pub => {
        publicationsMap.set(pub.title, pub);
    });

    // Clear existing content
    pubList.innerHTML = '';

    // Render each selected publication in Wikipedia style
    selectedData.selected_publications.forEach((title, index) => {
        const pub = publicationsMap.get(title);
        
        if (!pub) {
            console.warn(`Publication not found: "${title}"`);
            return;
        }

        const li = document.createElement('li');
        
        // Wikipedia-style publication entry
        // Title (plain text, bold - no hyperlink since [Paper] link is below)
        const titleSpan = document.createElement('span');
        titleSpan.className = 'pub-title';
        titleSpan.textContent = pub.title;
        li.appendChild(titleSpan);
        
        // Line break
        li.appendChild(document.createElement('br'));
        
        // Authors
        const authorsSpan = document.createElement('span');
        authorsSpan.className = 'pub-authors';
        authorsSpan.innerHTML = highlightAuthor(pub.authors);
        li.appendChild(authorsSpan);
        
        // Line break
        li.appendChild(document.createElement('br'));
        
        // Venue
        const venueSpan = document.createElement('span');
        venueSpan.className = 'pub-venue';
        venueSpan.textContent = pub.venue;
        li.appendChild(venueSpan);
        
        // Links
        if (pub.paper_url || pub.code_url || pub.homepage_url || pub.extra_code_urls || pub.media_links) {
            li.appendChild(document.createTextNode(' — '));
            const linksSpan = document.createElement('span');
            linksSpan.className = 'pub-links';
            
            if (pub.paper_url) {
                const paperLink = document.createElement('a');
                paperLink.href = pub.paper_url;
                paperLink.textContent = '[Paper]';
                paperLink.target = '_blank';
                paperLink.rel = 'noopener noreferrer';
                linksSpan.appendChild(paperLink);
            }

            if (pub.code_url) {
                if (pub.paper_url) {
                    linksSpan.appendChild(document.createTextNode(' '));
                }
                const codeLink = document.createElement('a');
                codeLink.href = pub.code_url;
                codeLink.textContent = '[Code]';
                codeLink.target = '_blank';
                codeLink.rel = 'noopener noreferrer';
                linksSpan.appendChild(codeLink);
            }

            if (pub.homepage_url) {
                if (pub.paper_url || pub.code_url) {
                    linksSpan.appendChild(document.createTextNode(' '));
                }
                const homepageLink = document.createElement('a');
                homepageLink.href = pub.homepage_url;
                homepageLink.textContent = '[Homepage]';
                homepageLink.target = '_blank';
                homepageLink.rel = 'noopener noreferrer';
                linksSpan.appendChild(homepageLink);
            }

            renderExtraLinks(linksSpan, pub);
            
            li.appendChild(linksSpan);
        }

        pubList.appendChild(li);
    });

    console.log(`Successfully loaded ${selectedData.selected_publications.length} selected publications from YAML`);
}

// Render all publications for publications.html (Wikipedia style)
async function loadAllPublications() {
    const data = await loadYAML('_data/publications.yaml');
    
    // Try Wikipedia-style selector first, then fallback
    let pubList = document.querySelector('.wiki-publications-full-list');
    if (!pubList) {
        pubList = document.querySelector('.pub-list');
    }
    
    if (!pubList) {
        console.error('Publications list element not found');
        return;
    }

    if (!data || !data.publications) {
        console.error('Failed to load all publications');
        pubList.innerHTML = `
            <li style="color: #ba0000;">
                Failed to load publications. Please check the console for details.
            </li>
        `;
        return;
    }

    // Clear existing content
    pubList.innerHTML = '';

    // Render each publication in Wikipedia style
    data.publications.forEach((pub, index) => {
        const li = document.createElement('li');

        // Title (plain text, bold - no hyperlink since [Paper] link is below)
        const titleSpan = document.createElement('span');
        titleSpan.className = 'wiki-pub-title-text';
        titleSpan.textContent = pub.title;
        li.appendChild(titleSpan);
        
        // Line break
        li.appendChild(document.createElement('br'));
        
        // Authors
        const authorsSpan = document.createElement('span');
        authorsSpan.className = 'wiki-pub-authors-text';
        authorsSpan.innerHTML = highlightAuthor(pub.authors);
        li.appendChild(authorsSpan);
        
        // Line break
        li.appendChild(document.createElement('br'));
        
        // Venue
        const venueSpan = document.createElement('span');
        venueSpan.className = 'wiki-pub-venue-text';
        venueSpan.textContent = pub.venue;
        li.appendChild(venueSpan);
        
        // Links
        if (pub.paper_url || pub.code_url || pub.homepage_url || pub.extra_code_urls || pub.media_links) {
            li.appendChild(document.createTextNode(' — '));
            
            if (pub.paper_url) {
                const paperLink = document.createElement('a');
                paperLink.href = pub.paper_url;
                paperLink.textContent = '[Paper]';
                paperLink.target = '_blank';
                paperLink.rel = 'noopener noreferrer';
                li.appendChild(paperLink);
            }

            if (pub.code_url) {
                if (pub.paper_url) {
                    li.appendChild(document.createTextNode(' '));
                }
                const codeLink = document.createElement('a');
                codeLink.href = pub.code_url;
                codeLink.textContent = '[Code]';
                codeLink.target = '_blank';
                codeLink.rel = 'noopener noreferrer';
                li.appendChild(codeLink);
            }

            if (pub.homepage_url) {
                if (pub.paper_url || pub.code_url) {
                    li.appendChild(document.createTextNode(' '));
                }
                const homepageLink = document.createElement('a');
                homepageLink.href = pub.homepage_url;
                homepageLink.textContent = '[Homepage]';
                homepageLink.target = '_blank';
                homepageLink.rel = 'noopener noreferrer';
                li.appendChild(homepageLink);
            }

            renderExtraLinks(li, pub);
        }

        pubList.appendChild(li);
    });

    console.log(`Successfully loaded ${data.publications.length} publications from YAML`);
}

// Auto-initialize based on page
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the index page (Wikipedia style or old style)
    if (document.querySelector('#pub-list') || document.querySelector('#publications')) {
        // Index page - load selected publications
        loadSelectedPublications();
    } 
    // Check for publications page
    else if (document.querySelector('.wiki-publications-full-list')) {
        // Publications page - load all publications (Wikipedia style)
        loadAllPublications();
    }
    else {
        // Check for old-style publications page
        const pageHeader = document.querySelector('.page-header h1');
        if (pageHeader && pageHeader.textContent.includes('Publication Full List')) {
            loadAllPublications();
        }
        // Check for Wikipedia-style publications page title
        const wikiPageTitle = document.querySelector('.wiki-page-title');
        if (wikiPageTitle && (wikiPageTitle.textContent.includes('Publication') || wikiPageTitle.textContent.includes('publication'))) {
            loadAllPublications();
        }
    }
});
