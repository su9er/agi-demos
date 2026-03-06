import React from 'react';
import { useCoAgent } from "@copilotkit/react-core";

interface SearchState {
  search_results: string[];
  status: "idle" | "searching" | "done";
}

export const Researcher = () => {
  const { state, setState } = useCoAgent<SearchState>({
    name: "research_agent",
    initialState: {
      search_results: [],
      status: "idle",
    },
  });

  return (
    <div className="p-4 border rounded shadow-sm bg-gray-50">
      <h3 className="text-lg font-semibold mb-2">Agent Status: {state.status}</h3>
      <div className="space-y-2">
        {state.search_results.length > 0 ? (
          <ul className="list-disc pl-5">
            {state.search_results.map((res, i) => (
              <li key={i} className="text-blue-600 underline cursor-pointer">
                {res}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-gray-500 italic">No search results yet.</p>
        )}
      </div>
      <button 
        className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
        onClick={() => setState({ ...state, status: "searching" })}
      >
        Sync Searching Status
      </button>
    </div>
  );
};
