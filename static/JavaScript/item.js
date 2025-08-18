document.addEventListener('DOMContentLoaded', () => {

    document.querySelector('ul#qtyDropdown').addEventListener('click', (event) => {

        document.querySelector('button#qtyDropdownTrigger')
            .textContent = 'Quantity: ' + event.target.textContent;
        document.querySelector('input[name="qty"]').value = event.target
            .textContent.trim();
        
    });

});
