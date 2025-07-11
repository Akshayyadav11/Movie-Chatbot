// Function to get the auth token from localStorage
function getAuthToken() {
    return localStorage.getItem('access_token');
}

// Function to check if user is authenticated
function isAuthenticated() {
    return !!getAuthToken();
}

// Function to redirect to login if not authenticated
function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

// Function to set up authenticated fetch
function authFetch(url, options = {}) {
    const token = getAuthToken();
    const headers = new Headers(options.headers || {});
    
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }
    
    return fetch(url, {
        ...options,
        headers
    });
}

// Check auth status on page load
document.addEventListener('DOMContentLoaded', function() {
    // Don't check auth on login page
    if (window.location.pathname === '/login') {
        // If already logged in, redirect to admin
        if (isAuthenticated()) {
            window.location.href = '/admin';
        }
        return;
    }
    
    // For protected pages, check auth
    if (window.location.pathname.startsWith('/admin')) {
        if (!isAuthenticated()) {
            window.location.href = '/login';
        }
    }
});
