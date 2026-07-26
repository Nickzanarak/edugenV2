import { ButtonHTMLAttributes, ReactNode } from "react";

export const PrimaryBtn = ({ 
  children, 
  className = "", 
  ...props 
}: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) => (
  <button 
    {...props} 
    className={`px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-sm disabled:opacity-50 ${className}`}
  >
    {children}
  </button>
);
