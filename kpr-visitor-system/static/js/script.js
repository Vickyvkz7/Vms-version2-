// KPR College Visitor Management System JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Real-time clock update
    function updateClock() {
        const now = new Date();
        const clockElement = document.getElementById('current-time');
        if (clockElement) {
            clockElement.textContent = now.toLocaleTimeString();
        }
    }
    
    setInterval(updateClock, 1000);
    updateClock();
    
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
    
    // Auto-format phone numbers
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length > 10) value = value.substring(0, 10);
            
            if (value.length > 6) {
                value = value.substring(0, 6) + '-' + value.substring(6);
            }
            if (value.length > 3) {
                value = value.substring(0, 3) + '-' + value.substring(3);
            }
            
            e.target.value = value;
        });
    });
    
    // Quick check-out confirmation
    const checkOutButtons = document.querySelectorAll('.checkout-btn');
    checkOutButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to check out this visitor?')) {
                e.preventDefault();
            }
        });
    });
    
    // Auto-refresh visitor list every 30 seconds
    if (window.location.pathname === '/visitors') {
        setInterval(function() {
            fetch('/api/visitors/today')
                .then(response => response.json())
                .then(data => {
                    // Update visitor count badge if exists
                    const badge = document.getElementById('current-visitors-badge');
                    if (badge) {
                        const checkedInCount = data.filter(v => v.status === 'checked_in').length;
                        badge.textContent = checkedInCount;
                    }
                });
        }, 30000);
    }
    
    // Print visitor pass
    window.printVisitorPass = function(visitorId) {
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <html>
                <head>
                    <title>KPR College Visitor Pass - ${visitorId}</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 20px; }
                        .pass { border: 2px solid #1a237e; padding: 20px; max-width: 400px; margin: 0 auto; }
                        .header { background: #1a237e; color: white; padding: 10px; margin: -20px -20px 20px; }
                        .qr-code { max-width: 150px; margin: 20px auto; }
                        .footer { margin-top: 20px; font-size: 12px; color: #666; }
                    </style>
                </head>
                <body>
                    <div class="pass">
                        <div class="header">
                            <h3>KPR College of Arts Science & Research</h3>
                            <h4>Visitor Pass</h4>
                        </div>
                        <p><strong>Visitor ID:</strong> ${visitorId}</p>
                        <div class="qr-code" id="qr-container"></div>
                        <p>This pass must be worn visibly at all times</p>
                        <div class="footer">
                            <p>Generated on: ${new Date().toLocaleString()}</p>
                        </div>
                    </div>
                </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.print();
    };
});

// Search functionality for visitor table
function searchVisitors() {
    const input = document.getElementById('searchInput');
    const filter = input.value.toUpperCase();
    const table = document.querySelector('.visitor-table');
    const rows = table.getElementsByTagName('tr');
    
    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const cells = row.getElementsByTagName('td');
        let found = false;
        
        for (let j = 0; j < cells.length; j++) {
            const cell = cells[j];
            if (cell) {
                const textValue = cell.textContent || cell.innerText;
                if (textValue.toUpperCase().indexOf(filter) > -1) {
                    found = true;
                    break;
                }
            }
        }
        
        if (found) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    }
}