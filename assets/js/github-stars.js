/**
 * GitHub Stars Dynamic Loader
 * Fetches real-time star counts from GitHub API
 */

// Repository configuration
const GITHUB_REPOS = [
    { owner: 'deepinsight', repo: 'insightface', selector: '.stars-insightface' },
    { owner: 'EvolvingLMMs-Lab', repo: 'LLaVA-OneVision-1.5', selector: '.stars-llava-onevision' },
    { owner: 'LLaVA-VL', repo: 'LLaVA-NeXT', selector: '.stars-llava-next' },
    { owner: 'deepglint', repo: 'unicom', selector: '.stars-unicom' },
    { owner: 'anxiangsir', repo: 'urban_seg', selector: '.stars-urban-seg' }
];

/**
 * Format star count with comma separators
 */
function formatStarCount(count) {
    return count.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Fetch star count from GitHub API with rate limit handling
 */
async function fetchStarCount(owner, repo) {
    try {
        const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`);
        
        // Check rate limit headers
        const remaining = response.headers.get('X-RateLimit-Remaining');
        if (remaining === '0') {
            console.warn('GitHub API rate limit exceeded');
            return null;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data.stargazers_count;
    } catch (error) {
        console.error(`Error fetching stars for ${owner}/${repo}:`, error);
        return null;
    }
}

/**
 * Update star count in the DOM
 */
function updateStarCount(selector, count) {
    const elements = document.querySelectorAll(selector);
    elements.forEach(element => {
        if (count !== null) {
            element.textContent = `⭐ ${formatStarCount(count)} Stars`;
        }
    });
}

/**
 * Load all star counts with staggered requests to avoid rate limiting
 */
async function loadAllStarCounts() {
    // Fetch star counts with a small delay between requests to avoid rate limiting
    for (const { owner, repo, selector } of GITHUB_REPOS) {
        const count = await fetchStarCount(owner, repo);
        updateStarCount(selector, count);
        // Small delay between requests (200ms) to be respectful of API limits
        await new Promise(resolve => setTimeout(resolve, 200));
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadAllStarCounts);
} else {
    loadAllStarCounts();
}
