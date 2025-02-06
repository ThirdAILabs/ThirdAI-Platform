import React from 'react';

interface LogoLayoutProps {
  logoSrc: string;
  workflowName?: string; // Optional since workflowName might not always be present
}

const LogoLayout: React.FC<LogoLayoutProps> = ({ logoSrc, workflowName }) => {
  return (
    <div className="fixed top-0 left-0 flex flex-col items-start p-2 z-50">
      <a href="/" className="flex items-center mb-2">
        <img src={logoSrc} alt="Logo" className="h-12 mr-3 object-contain hover:cursor-pointer" />
      </a>
      {workflowName && <div className="text-sm font-medium text-gray-700 ml-1">{workflowName}</div>}
    </div>
  );
};

export default LogoLayout;
