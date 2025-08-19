document.addEventListener('DOMContentLoaded', () => {
    const originalContent = document.querySelector('div.row').innerHTML;
    
    const formatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    });

    document.querySelector('input[type="search"]').addEventListener('input', async (event) => {
        const response = await fetch("/api/search?q=" + event.target.value);
        const items = await response.json();
        let html = ``;

        for (const item of items) {
            html +=
                `
                <div class="col">

                    <div class="card h-100">

                        <img alt="${item.title}" class="card-img-top" src="/static/images/${item.filename}">

                        <div class="card-body">
                            <h5 class="card-title">${item.title}</h5>
                            <p class="card-text">${item.description}</p>
                            <p class="card-text">Price: ${formatter.format(item.price)}</p>
                            <a class="stretched-link" href="/item/${item.id}"></a>
                        </div>

                    </div>

                </div>
                `;
        }

        if (event.target.value) {
            document.querySelector('div.row').innerHTML = html;
        } else {
            document.querySelector('div.row').innerHTML = originalContent;
        }
    });
});