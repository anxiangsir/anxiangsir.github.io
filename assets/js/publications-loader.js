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
    // Load both files: selected_publications.yaml (titles only) and publications.yaml (full data)
    const [selectedData, allData] = await Promise.all([
        loadYAML('_data/selected_publications.yaml'),
        loadYAML('_data/publications.yaml')
    ]);
    
    const pubContainer = document.querySelector('#publications-container');
    if (!pubContainer) {
        console.error('Publications container element not found');
        return;
    }

    if (!selectedData || !selectedData.selected_publications || !allData || !allData.publications) {
        console.error('Failed to load publications data');
        pubContainer.innerHTML = `<p style="color: #856404;">⚠️ Failed to load selected publications</p>`;
        return;
    }

    // Create a map of publications by title for fast lookup
    const publicationsMap = new Map();
    allData.publications.forEach(pub => {
        publicationsMap.set(pub.title, pub);
    });

    // Clear existing content
    pubContainer.innerHTML = '';

    // Render each selected publication by looking up from publications.yaml
    selectedData.selected_publications.forEach((title, index) => {
        const pub = publicationsMap.get(title);
        
        if (!pub) {
            console.warn(`Publication not found: "${title}"`);
            return;
        }

        const pubBlock = document.createElement('div');
        pubBlock.className = 'pub-block';

        // Title
        const titleEl = document.createElement('h3');
        titleEl.textContent = pub.title;
        pubBlock.appendChild(titleEl);

        // Authors
        const authors = document.createElement('div');
        authors.className = 'authors';
        authors.innerHTML = highlightAuthor(pub.authors);
        pubBlock.appendChild(authors);

        // Venue
        const venue = document.createElement('div');
        venue.className = 'venue';
        venue.textContent = pub.venue;
        pubBlock.appendChild(venue);

        // Links
        const linksDiv = document.createElement('div');
        linksDiv.style.marginTop = '10px';

        if (pub.paper_url) {
            const paperLink = document.createElement('a');
            paperLink.href = pub.paper_url;
            paperLink.textContent = '[Paper]';
            paperLink.target = '_blank';
            paperLink.rel = 'noopener noreferrer';
            linksDiv.appendChild(paperLink);
        }

        if (pub.code_url) {
            const codeLink = document.createElement('a');
            codeLink.href = pub.code_url;
            codeLink.textContent = '[Code]';
            codeLink.target = '_blank';
            codeLink.rel = 'noopener noreferrer';
            linksDiv.appendChild(codeLink);
        }

        pubBlock.appendChild(linksDiv);
        pubContainer.appendChild(pubBlock);
    });

    console.log(`Successfully loaded ${selectedData.selected_publications.length} selected publications from YAML`);
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
    // Check if we're on the index page
    if (document.querySelector('#publications-container')) {
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
