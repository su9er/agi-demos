import React from 'react';
import { useCopilotAction } from "@copilotkit/react-core";
import { ProductCard } from "./ProductCard";

export const ProductDisplay = () => {
  useCopilotAction({
    name: "show_product",
    description: "Displays a product card to the user.",
    parameters: [
      {
        name: "product_id",
        type: "string",
        description: "The ID of the product to show.",
        required: true,
      },
      {
        name: "name",
        type: "string",
        description: "The name of the product.",
      },
      {
        name: "price",
        type: "number",
        description: "The price of the product.",
      }
    ],
    render: ({ args, status }) => {
      const { product_id, name, price } = args;
      
      return (
        <div className="my-4 p-4 border border-dashed border-gray-300 rounded bg-gray-50">
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-3 h-3 rounded-full ${status === 'in_progress' ? 'bg-yellow-400 animate-pulse' : 'bg-green-500'}`} />
            <span className="text-xs font-mono uppercase tracking-wider text-gray-500">
              Agent Action: {status}
            </span>
          </div>
          
          <ProductCard 
            id={product_id || "unknown"} 
            name={name || "Product Loading..."} 
            price={price || 0} 
          />
          
          {status === "complete" && (
            <div className="mt-3 text-xs text-right text-gray-400 italic">
              * Verified by Research Agent
            </div>
          )}
        </div>
      );
    },
    handler: async (args) => {
      console.log("Action Handled:", args.product_id);
      return `Product ${args.product_id} is now visible on the screen.`;
    },
  });

  return null;
};
