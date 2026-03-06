import React from 'react';

interface ProductCardProps {
  id: string;
  name: string;
  price: number;
}

export const ProductCard: React.FC<ProductCardProps> = ({ id, name, price }) => (
  <div className="p-4 border border-blue-200 rounded-lg shadow-sm bg-white hover:border-blue-400 transition">
    <div className="flex justify-between items-start mb-2">
      <h4 className="text-xl font-bold text-gray-800">{name}</h4>
      <span className="bg-green-100 text-green-800 text-sm font-semibold px-2.5 py-0.5 rounded">
        ${price.toFixed(2)}
      </span>
    </div>
    <p className="text-sm text-gray-500 mb-4">Product ID: {id}</p>
    <button className="w-full py-2 bg-blue-600 text-white rounded font-medium hover:bg-blue-700">
      Add to Cart
    </button>
  </div>
);
