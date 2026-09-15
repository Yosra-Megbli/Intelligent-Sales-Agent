import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export const Skeleton: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => {
  return (
    <div
      className={cn(
        "animate-pulse rounded-[0.5rem] bg-[var(--border)] opacity-70",
        className
      )}
      {...props}
    />
  );
};
