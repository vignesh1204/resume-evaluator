import React from "react";

const VARIANTS = {
  emerald: [
    "bg-emerald-500/95 text-white",
    "shadow-[0_10px_30px_rgba(16,185,129,0.25)]",
    "ring-1 ring-emerald-200/20",
    "hover:bg-emerald-400 hover:shadow-[0_14px_38px_rgba(16,185,129,0.30)]",
    "focus-visible:ring-emerald-200/60",
    "disabled:hover:bg-emerald-500/95",
  ].join(" "),
  noir: [
    "noir-btn text-white",
    "hover:shadow-[0_16px_46px_rgba(0,0,0,0.38)]",
    "focus-visible:ring-2 focus-visible:ring-white/25 focus-visible:ring-offset-2 focus-visible:ring-offset-black/40",
  ].join(" "),
};

const CustomButton = ({
  text,
  onClick,
  disabled,
  type = "button",
  className = "",
  variant = "noir", // default to noir so your app stays consistent
}) => {
  const variantCls = VARIANTS[variant] || VARIANTS.noir;

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={[
        "inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3",
        "text-sm sm:text-base font-semibold tracking-tight",
        "transition-all duration-200 select-none",
        "active:translate-y-[1px]",
        "focus:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:active:translate-y-0",
        variantCls,
        className,
      ].join(" ")}
    >
      {text}
    </button>
  );
};

export default CustomButton;