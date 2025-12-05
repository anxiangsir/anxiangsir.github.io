/**
 * Publications Loader - Loads publications from JSON files and renders them
 */

// Load JSON data from file
async function loadJSON(url) {
    try {
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error('Error loading JSON:', error);
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
    const data = await loadJSON('_data/selected_publications.json');
    if (!data || !data.publications) {
        console.error('Failed to load selected publications');
        return;
    }

    const pubList = document.querySelector('#publications + .pub-list');
    if (!pubList) {
        console.error('Publications list element not found');
        return;
    }

    // Clear existing content
    pubList.innerHTML = '';

    // Render each publication
    data.publications.forEach(pub => {
        const li = document.createElement('li');
        
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
            linkBadges.appendChild(paperLink);
        }

        if (pub.code_url) {
            const codeLink = document.createElement('a');
            codeLink.href = pub.code_url;
            codeLink.className = 'badge-link';
            codeLink.textContent = 'Code';
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
}

// Render all publications for publications.html
async function loadAllPublications() {
    const data = await loadJSON('_data/publications.json');
    if (!data || !data.publications) {
        console.error('Failed to load all publications');
        return;
    }

    const pubList = document.querySelector('.pub-list');
    if (!pubList) {
        console.error('Publications list element not found');
        return;
    }

    // Clear existing content
    pubList.innerHTML = '';

    // Render each publication
    data.publications.forEach(pub => {
        const li = document.createElement('li');
        li.className = 'pub-item';

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
}

// Auto-initialize based on page
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the index page or publications page
    if (document.querySelector('#publications')) {
        // Index page - load selected publications
        loadSelectedPublications();
    } else if (document.querySelector('.page-header h1') && 
               document.querySelector('.page-header h1').textContent.includes('Publication Full List')) {
        // Publications page - load all publications
        loadAllPublications();
    }
});
