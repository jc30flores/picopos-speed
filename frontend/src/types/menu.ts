// Types for Menu Management


export interface BxgyConfig {
  rules: Array<{
    id: string;
    mode?: 'same_pool' | 'separate_pool';
    buy: { qty: number; selector: { mode: 'products' | 'categories'; product_ids: number[]; category_ids: number[] } };
    get: {
      qty: number;
      selector: { mode: 'products' | 'categories'; product_ids: number[]; category_ids: number[] };
      reward: { type: 'percent' | 'fixed_amount' | 'fixed_price'; value: number; include_paid_modifiers?: boolean };
      apply_to: 'cheapest' | 'most_expensive';
      include_paid_modifiers?: boolean;
    };
    limits: { max_applications_per_ticket: number };
  }>;
  global?: { exclude_disposables?: boolean; stacking?: 'none' | 'allow_with_stackables'; overlap_buy_get?: boolean };
}
export interface Discount {
  id: string;
  name: string;
  description?: string;
  type: 'percent' | 'fixed' | 'bxgy';
  value: number;
  appliesTo: 'order' | 'categories' | 'products';
  targetCategories?: string[];
  targetProducts?: string[];
  targetProductIds?: number[];
  days: number[]; // 0-6 (Mon-Sun)
  startTime?: string;
  endTime?: string;
  serviceTypes: string[];
  minAmount?: number | null;
  autoApply: boolean;
  active: boolean;
  priority?: number;
  stackable?: boolean;
  bxgyConfig?: BxgyConfig;
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
