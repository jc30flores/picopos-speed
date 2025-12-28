// Types for Menu Management

export interface Discount {
  id: string;
  name: string;
  description?: string;
  type: 'percentage' | 'fixed' | 'happy-hour' | 'category';
  value: number;
  appliesTo: 'ticket' | 'categories' | 'products';
  targetCategories?: string[];
  targetProducts?: string[];
  days: number[]; // 0-6 (Sun-Sat)
  startTime?: string;
  endTime?: string;
  serviceTypes: ('dine-in' | 'takeout' | 'delivery' | 'kiosk')[];
  minAmount?: number;
  requiresApproval: boolean;
  autoApply: boolean;
  active: boolean;
}

export interface ModifierOption {
  id: string;
  name: string;
  price: number;
  defaultSelected: boolean;
}

export interface ModifierGroupForm {
  id: string;
  name: string;
  required: boolean;
  minSelection: number;
  maxSelection: number;
  options: ModifierOption[];
}
