const orders = [
    { id: 'A1001', status: '배송중' },
    { id: 'A1002', status: '배송완료' },
    { id: 'A1003', status: '주문접수' },
];

const orderListEl = document.querySelector('.order-list');
const filterButtonsEl = document.querySelector('.filter-buttons');

function renderOrders(list) {
    const cardsHtml = list.map(order => `
    <div class="order-card">
        <p class="order-id">주문번호: ${order.id}</p>
        <p class="order-status">${order.status}</p>
    </div>
    `).join('');

    orderListEl.innerHTML = cardsHtml;
}

filterButtonsEl.addEventListener('click', (event) => {
    const status = event.target.dataset.status;
    if (!status) return;

    if (status === 'all'){
        renderOrders(orders);
    } else {
        const filtered = orders.filter((order) => order.status === status);
        renderOrders(filtered);
    }
});

renderOrders(orders);
