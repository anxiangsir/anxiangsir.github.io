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
 * Fetch star count from GitHub API
 */
async function fetchStarCount(owner, repo) {
    try {
        const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`);
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
 * Load all star counts
 */
async function loadAllStarCounts() {
    // Fetch all star counts in parallel
    const promises = GITHUB_REPOS.map(async ({ owner, repo, selector }) => {
        const count = await fetchStarCount(owner, repo);
        updateStarCount(selector, count);
    });

    await Promise.all(promises);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadAllStarCounts);
} else {
    loadAllStarCounts();
}
