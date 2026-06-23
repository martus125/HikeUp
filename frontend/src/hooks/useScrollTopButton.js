//przycisk powrotu do strony głównej
import { useEffect, useState } from "react";

export function useScrollTopButton(offset = 400) {
  const [showScrollTop, setShowScrollTop] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setShowScrollTop(window.scrollY > offset);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [offset]);

  return showScrollTop;
}
