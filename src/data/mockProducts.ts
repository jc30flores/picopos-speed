export interface Modifier {
  id: string;
  name: string;
  price: number;
}

export interface ModifierGroup {
  id: string;
  name: string;
  required: boolean;
  minSelection: number;
  maxSelection: number;
  modifiers: Modifier[];
}

export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  category: string;
  image: string;
  available: boolean;
  modifierGroups?: string[];
}

export const modifierGroups: ModifierGroup[] = [
  {
    id: "proteins",
    name: "Proteína",
    required: true,
    minSelection: 1,
    maxSelection: 1,
    modifiers: [
      { id: "carne-asada", name: "Carne Asada", price: 0 },
      { id: "pollo", name: "Pollo", price: 0 },
      { id: "carnitas", name: "Carnitas", price: 0 },
      { id: "pastor", name: "Pastor", price: 0 },
      { id: "pescado", name: "Pescado", price: 1.5 },
    ],
  },
  {
    id: "toppings",
    name: "Toppings",
    required: false,
    minSelection: 0,
    maxSelection: 5,
    modifiers: [
      { id: "guacamole", name: "Guacamole", price: 1.5 },
      { id: "queso", name: "Queso", price: 1 },
      { id: "crema", name: "Crema", price: 0.5 },
      { id: "pico", name: "Pico de Gallo", price: 0 },
      { id: "jalapeños", name: "Jalapeños", price: 0 },
      { id: "cilantro", name: "Cilantro", price: 0 },
      { id: "cebolla", name: "Cebolla", price: 0 },
    ],
  },
  {
    id: "salsa",
    name: "Salsa",
    required: false,
    minSelection: 0,
    maxSelection: 3,
    modifiers: [
      { id: "verde", name: "Verde", price: 0 },
      { id: "roja", name: "Roja", price: 0 },
      { id: "habanero", name: "Habanero", price: 0 },
      { id: "chipotle", name: "Chipotle", price: 0 },
    ],
  },
  {
    id: "size",
    name: "Tamaño",
    required: true,
    minSelection: 1,
    maxSelection: 1,
    modifiers: [
      { id: "regular", name: "Regular", price: 0 },
      { id: "grande", name: "Grande", price: 2 },
    ],
  },
];

export const mockProducts: Product[] = [
  {
    id: "taco-1",
    name: "Taco de Carne Asada",
    description: "Taco clásico con carne asada, cebolla y cilantro",
    price: 3.5,
    category: "Tacos",
    image: "🌮",
    available: true,
    modifierGroups: ["proteins", "toppings", "salsa"],
  },
  {
    id: "taco-2",
    name: "Taco de Pollo",
    description: "Taco con pollo marinado y pico de gallo",
    price: 3.25,
    category: "Tacos",
    image: "🌮",
    available: true,
    modifierGroups: ["proteins", "toppings", "salsa"],
  },
  {
    id: "burrito-1",
    name: "Burrito Supreme",
    description: "Burrito con arroz, frijoles, queso y tu proteína favorita",
    price: 8.99,
    category: "Burritos",
    image: "🌯",
    available: true,
    modifierGroups: ["proteins", "toppings", "salsa", "size"],
  },
  {
    id: "burrito-2",
    name: "Burrito California",
    description: "Burrito con papas fritas, queso y guacamole",
    price: 9.99,
    category: "Burritos",
    image: "🌯",
    available: true,
    modifierGroups: ["proteins", "toppings", "size"],
  },
  {
    id: "bowl-1",
    name: "Bowl de Proteína",
    description: "Bowl con arroz, frijoles, lechuga y tu proteína",
    price: 9.5,
    category: "Bowls",
    image: "🥗",
    available: true,
    modifierGroups: ["proteins", "toppings", "salsa"],
  },
  {
    id: "bowl-2",
    name: "Bowl Vegano",
    description: "Bowl con verduras asadas, arroz y frijoles",
    price: 8.5,
    category: "Bowls",
    image: "🥗",
    available: true,
    modifierGroups: ["toppings", "salsa"],
  },
  {
    id: "quesadilla-1",
    name: "Quesadilla de Queso",
    description: "Quesadilla clásica con queso fundido",
    price: 5.99,
    category: "Quesadillas",
    image: "🧀",
    available: true,
    modifierGroups: ["proteins", "toppings"],
  },
  {
    id: "drink-1",
    name: "Agua de Horchata",
    description: "Refrescante agua de horchata casera",
    price: 2.5,
    category: "Bebidas",
    image: "🥤",
    available: true,
  },
  {
    id: "drink-2",
    name: "Agua de Jamaica",
    description: "Agua de jamaica fría",
    price: 2.5,
    category: "Bebidas",
    image: "🥤",
    available: true,
  },
  {
    id: "drink-3",
    name: "Coca-Cola",
    description: "Refresco de cola",
    price: 2,
    category: "Bebidas",
    image: "🥤",
    available: true,
  },
  {
    id: "side-1",
    name: "Chips & Guacamole",
    description: "Chips de tortilla con guacamole fresco",
    price: 4.99,
    category: "Acompañamientos",
    image: "🥑",
    available: true,
  },
  {
    id: "side-2",
    name: "Chips & Queso",
    description: "Chips de tortilla con queso fundido",
    price: 4.5,
    category: "Acompañamientos",
    image: "🧀",
    available: true,
  },
  {
    id: "dessert-1",
    name: "Churros",
    description: "Churros crujientes con azúcar y canela",
    price: 3.99,
    category: "Postres",
    image: "🍩",
    available: true,
  },
  {
    id: "dessert-2",
    name: "Flan",
    description: "Flan casero de vainilla",
    price: 3.5,
    category: "Postres",
    image: "🍮",
    available: true,
  },
];

export const categories = [
  "Todos",
  "Tacos",
  "Burritos",
  "Bowls",
  "Quesadillas",
  "Bebidas",
  "Acompañamientos",
  "Postres",
];
