// Product catalog search with prefix matching.
export interface Product {
  sku: string;
  name: string;
}

const CATALOG: Product[] = [
  { sku: "A1", name: "Trail shoes" },
  { sku: "B2", name: "Rain jacket" },
];

export function searchProducts(query: string): Product[] {
  const q = query.toLowerCase();
  return CATALOG.filter((p) => p.name.toLowerCase().includes(q));
}
