/**
 * Navigation functionality for Apple-style navigation
 */
document.addEventListener('DOMContentLoaded', function() {
    // Update last modified date
    const lastModified = document.getElementById('last-modified');
    if (lastModified) {
        lastModified.textContent = new Date().toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
    }

    // Mobile menu toggle
    const navToggle = document.querySelector('.apple-nav-toggle');
    const mobileMenu = document.querySelector('.apple-mobile-menu');
    
    if (navToggle && mobileMenu) {
        navToggle.addEventListener('click', function() {
            navToggle.classList.toggle('active');
            mobileMenu.classList.toggle('active');
        });

        // Close menu when clicking a link
        mobileMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', function() {
                navToggle.classList.remove('active');
                mobileMenu.classList.remove('active');
            });
        });
    }
});
