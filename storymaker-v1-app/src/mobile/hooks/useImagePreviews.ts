import { useEffect, useMemo } from "react";

export function useImagePreviews(images: File[]) {
  const imagePreviews = useMemo(() => images.map((file) => ({ file, url: URL.createObjectURL(file) })), [images]);

  useEffect(() => {
    return () => imagePreviews.forEach((item) => URL.revokeObjectURL(item.url));
  }, [imagePreviews]);

  return imagePreviews;
}
