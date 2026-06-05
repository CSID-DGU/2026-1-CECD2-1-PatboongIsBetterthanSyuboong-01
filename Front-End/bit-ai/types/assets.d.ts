declare module "*.svg" {
  import * as React from "react";
  const ReactComponent: React.FC<React.SVGProps<SVGSVGElement>>;
  export default ReactComponent;
}
declare module "*.png" { const src: string; export default src; }
declare module "*.jpg" { const src: string; export default src; }
declare module "*.jpeg" { const src: string; export default src; }
declare module "*.gif" { const src: string; export default src; }
declare module "*.webp" { const src: string; export default src; }
declare module "*.bmp" { const src: string; export default src; }
declare module "*.avif" { const src: string; export default src; }


