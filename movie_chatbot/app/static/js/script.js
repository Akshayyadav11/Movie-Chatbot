// Additional frontend functionality can be added here
document.addEventListener('DOMContentLoaded', function() {
    // Check for admin token and redirect to admin page if present
    const token = localStorage.getItem('access_token');
    if (token && window.location.pathname === '/') {
        // Verify token and redirect if admin
        fetch('/api/admin/report', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(response => {
            if (response.ok) {
                window.location.href = '/admin';
            }
        })
        .catch(error => {
            console.error('Error verifying token:', error);
            localStorage.removeItem('access_token');
        });
    }
    
    // Logout functionality
    if (window.location.pathname === '/logout') {
        localStorage.removeItem('access_token');
        window.location.href = '/';
    }
});