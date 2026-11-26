"use client";

import { useEffect, useRef, useState } from "react";

/** O navegador pede a fotografia. O servidor da aplicação não a transfere. */
export function PublicPhoto({ src, alt }: { src: string; alt: string }) {
  const image = useRef<HTMLImageElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const node = image.current;
    // A falha pode ocorrer antes da hidratação, quando onError ainda não está ligado.
    if (node?.complete && node.naturalWidth === 0) setFailed(true);
  }, [src]);

  if (failed) return null;

  return (
    <img
      ref={image}
      className="product-photo"
      src={src}
      alt={alt}
      width={280}
      height={180}
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}
