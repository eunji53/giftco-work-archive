type OrderStatus = '배송중' | '배송완료' | '주문접수';

interface Order {
  id: string;
  status: OrderStatus;
}

const orders: Order[] = [
  { id: 'A1001', status: '배송중' },
  { id: 'A1002', status: '배송완료' },
  { id: 'A1003', status: '주문접수' },
];