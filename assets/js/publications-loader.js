/**
 * Publications Loader - Loads publications from YAML files and renders them
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

// Render selected publications for index.html
async function loadSelectedPublications() {
    const data = await loadYAML('_data/selected_publications.yaml');
    
    const pubList = document.querySelector('#publications + .pub-list');
    if (!pubList) {
        console.error('Publications list element not found');
        return;
    }

    if (!data || !data.publications) {
        console.error('Failed to load selected publications');
        pubList.innerHTML = `
            <li style="text-align: center; padding: 40px; background: #fff3cd; border-color: #ffc107;">
                <div style="color: #856404;">
                    <strong>⚠️ Failed to load selected publications</strong>
                    <div style="margin-top: 8px; font-size: 0.9rem;">
                        Could not load publications from YAML file. Please check the console for details.
                    </div>
                </div>
            </li>
        `;
        return;
    }

    // Clear existing content
    pubList.innerHTML = '';

    // Render each publication
    data.publications.forEach((pub, index) => {
        const li = document.createElement('li');
        // Add animation delay for stagger effect
        li.style.animationDelay = `${index * 0.1}s`;
        
        const pubEntry = document.createElement('div');
        pubEntry.className = 'publication-entry';

        // Add preview image if available
        if (pub.preview_image) {
            const img = document.createElement('img');
            img.src = pub.preview_image;
            img.alt = 'Paper Preview';
            img.onerror = function() { this.style.display = 'none'; };
            pubEntry.appendChild(img);
        }

        // Create content div
        const pubContent = document.createElement('div');
        pubContent.className = 'pub-content';

        // Title
        const title = document.createElement('span');
        title.className = 'pub-title';
        title.textContent = pub.title;
        pubContent.appendChild(title);

        // Authors
        const authors = document.createElement('span');
        authors.className = 'pub-authors';
        authors.innerHTML = highlightAuthor(pub.authors);
        pubContent.appendChild(authors);

        // Links and venue
        const linkBadges = document.createElement('div');
        linkBadges.className = 'link-badges';

        if (pub.paper_url) {
            const paperLink = document.createElement('a');
            paperLink.href = pub.paper_url;
            paperLink.className = 'badge-link';
            paperLink.textContent = 'Paper';
            paperLink.target = '_blank';
            paperLink.rel = 'noopener noreferrer';
            linkBadges.appendChild(paperLink);
        }

        if (pub.code_url) {
            const codeLink = document.createElement('a');
            codeLink.href = pub.code_url;
            codeLink.className = 'badge-link';
            codeLink.textContent = 'Code';
            codeLink.target = '_blank';
            codeLink.rel = 'noopener noreferrer';
            linkBadges.appendChild(codeLink);
        }

        const venue = document.createElement('span');
        venue.className = 'pub-venue';
        venue.textContent = pub.venue;
        linkBadges.appendChild(venue);

        pubContent.appendChild(linkBadges);
        pubEntry.appendChild(pubContent);
        li.appendChild(pubEntry);
        pubList.appendChild(li);
    });

    console.log(`Successfully loaded ${data.publications.length} selected publications from YAML`);
}

// Render all publications for publications.html
async function loadAllPublications() {
    const data = await loadYAML('_data/publications.yaml');
    
    const pubList = document.querySelector('.pub-list');
    if (!pubList) {
        console.error('Publications list element not found');
        return;
    }

    if (!data || !data.publications) {
        console.error('Failed to load all publications');
        pubList.innerHTML = `
            <li class="pub-item" style="text-align: center; padding: 40px; background: #fff3cd; border-color: #ffc107;">
                <div style="color: #856404;">
                    <strong>⚠️ Failed to load publications</strong>
                    <div style="margin-top: 8px; font-size: 0.9rem;">
                        Could not load publications from YAML file. Please check the console for details.
                    </div>
                </div>
            </li>
        `;
        return;
    }

    // Clear existing content
    pubList.innerHTML = '';

    // Render each publication
    data.publications.forEach((pub, index) => {
        const li = document.createElement('li');
        li.className = 'pub-item';
        // Add animation delay for stagger effect
        li.style.animationDelay = `${index * 0.05}s`;

        const title = document.createElement('div');
        title.className = 'pub-title';
        title.textContent = pub.title;
        li.appendChild(title);

        const authors = document.createElement('div');
        authors.className = 'pub-authors';
        authors.innerHTML = highlightAuthor(pub.authors);
        li.appendChild(authors);

        const venue = document.createElement('div');
        venue.className = 'pub-venue';
        venue.textContent = pub.venue;
        li.appendChild(venue);

        pubList.appendChild(li);
    });

    console.log(`Successfully loaded ${data.publications.length} publications from YAML`);
}

// Auto-initialize based on page
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the index page or publications page
    if (document.querySelector('#publications')) {
        // Index page - load selected publications
        loadSelectedPublications();
    } else {
        // Check for publications page
        const pageHeader = document.querySelector('.page-header h1');
        if (pageHeader && pageHeader.textContent.includes('Publication Full List')) {
            // Publications page - load all publications
            loadAllPublications();
        }
    }
});
