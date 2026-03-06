import React from 'react';
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { Researcher } from "./components/Researcher";
import { ProductDisplay } from "./components/ProductDisplay";
import "@copilotkit/react-ui/styles.css";

function App() {
  return (
    <CopilotKit runtimeUrl="http://localhost:8000/copilotkit">
      <CopilotSidebar
        defaultOpen={true}
        instructions="Help users search for products and display them as cards."
      >
        <div className="p-6">
          <h1 className="text-3xl font-extrabold text-gray-900 mb-6">
            A2UI Protocol Demo
          </h1>
          <p className="text-gray-600 mb-8 max-w-prose leading-relaxed">
            This application demonstrates state synchronization and generative UI using 
            the AG-UI protocol with CopilotKit.
          </p>
          
          <div className="max-w-md">
            <Researcher />
            <ProductDisplay />
          </div>
        </div>
      </CopilotSidebar>
    </CopilotKit>
  );
}

export default App;
