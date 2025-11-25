document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const tables = [
        document.getElementById('wardenTable'),
        document.getElementById('supportStaffTable'),
        document.getElementById('hosteliteTable')
    ];

    searchInput.addEventListener('input', function() {
        const searchTerm = searchInput.value.toLowerCase();

        tables.forEach(table => {
            const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
            for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                const userId = row.cells[0].textContent.toLowerCase();
                const name = row.cells[2].textContent.toLowerCase();
                const contact = row.cells[4].textContent.toLowerCase();
                const email = row.cells[5].textContent.toLowerCase();

                if (
                    userId.includes(searchTerm) ||
                    name.includes(searchTerm) ||
                    contact.includes(searchTerm) ||
                    email.includes(searchTerm)
                ) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            }
        });
    });
});