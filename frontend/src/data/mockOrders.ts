export interface OrderItem {
  id: string;
  productName: string;
  quantity: number;
  modifiers: string[];
  price: number;
}

export interface Order {
  id: string;
  orderNumber: number;
  items: OrderItem[];
  total: number;
  status: "new" | "preparing" | "ready" | "delivered";
  serviceType: "dine-in" | "takeout" | "delivery";
  createdAt: Date;
  prepTime: number; // minutes elapsed
  customerName?: string;
}

export const mockOrders: Order[] = [
  {
    id: "order-1",
    orderNumber: 101,
    items: [
      {
        id: "item-1",
        productName: "Burrito Supreme",
        quantity: 2,
        modifiers: ["Carne Asada", "Guacamole", "Queso", "Salsa Verde"],
        price: 8.99,
      },
      {
        id: "item-2",
        productName: "Coca-Cola",
        quantity: 2,
        modifiers: [],
        price: 2,
      },
    ],
    total: 21.98,
    status: "preparing",
    serviceType: "dine-in",
    createdAt: new Date(Date.now() - 8 * 60000), // 8 minutes ago
    prepTime: 8,
    customerName: "María G.",
  },
  {
    id: "order-2",
    orderNumber: 102,
    items: [
      {
        id: "item-3",
        productName: "Taco de Carne Asada",
        quantity: 4,
        modifiers: ["Carne Asada", "Cilantro", "Cebolla"],
        price: 3.5,
      },
      {
        id: "item-4",
        productName: "Agua de Horchata",
        quantity: 1,
        modifiers: [],
        price: 2.5,
      },
    ],
    total: 16.5,
    status: "new",
    serviceType: "takeout",
    createdAt: new Date(Date.now() - 2 * 60000), // 2 minutes ago
    prepTime: 2,
    customerName: "Carlos R.",
  },
  {
    id: "order-3",
    orderNumber: 103,
    items: [
      {
        id: "item-5",
        productName: "Bowl de Proteína",
        quantity: 1,
        modifiers: ["Pollo", "Guacamole", "Pico de Gallo", "Salsa Chipotle"],
        price: 9.5,
      },
    ],
    total: 9.5,
    status: "ready",
    serviceType: "dine-in",
    createdAt: new Date(Date.now() - 15 * 60000), // 15 minutes ago
    prepTime: 15,
    customerName: "Ana L.",
  },
  {
    id: "order-4",
    orderNumber: 104,
    items: [
      {
        id: "item-6",
        productName: "Burrito California",
        quantity: 1,
        modifiers: ["Pastor", "Grande", "Queso", "Guacamole"],
        price: 11.99,
      },
      {
        id: "item-7",
        productName: "Chips & Guacamole",
        quantity: 1,
        modifiers: [],
        price: 4.99,
      },
    ],
    total: 16.98,
    status: "preparing",
    serviceType: "delivery",
    createdAt: new Date(Date.now() - 12 * 60000), // 12 minutes ago
    prepTime: 12,
  },
];
