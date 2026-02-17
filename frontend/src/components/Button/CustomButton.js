import React from "react";

const CustomButton = ({
  text,
  onClick,
  disabled,
  type = "button",
  className = "",
}) => {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={[
        // Base
        "inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3",
        "text-sm sm:text-base font-semibold tracking-tight",
        "transition-all duration-200",
        "select-none",
        // Primary look
        "bg-emerald-500/95 text-white",
        "shadow-[0_10px_30px_rgba(16,185,129,0.25)]",
        "ring-1 ring-emerald-200/20",
        // Hover/active
        "hover:bg-emerald-400 hover:shadow-[0_14px_38px_rgba(16,185,129,0.30)]",
        "active:translate-y-[1px] active:shadow-[0_8px_24px_rgba(16,185,129,0.22)]",
        // Focus
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-200/60 focus-visible:ring-offset-2 focus-visible:ring-offset-black/30",
        // Disabled
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-emerald-500/95 disabled:shadow-none disabled:active:translate-y-0",
        className,
      ].join(" ")}
    >
      {text}
    </button>
  );
};

export default CustomButton;
