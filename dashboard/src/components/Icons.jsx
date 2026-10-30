import {
  ArrowLeftRight,
  FileText,
  Table2,
  Presentation,
  PenTool,
  Database,
  Sigma,
  Clapperboard,
  CirclePlay,
} from "lucide-react";
const icons = {
  convert: ArrowLeftRight,
  pages: FileText,
  tables: Table2,
  dazzle: Presentation,
  sketch: PenTool,
  organize: Database,
  formulaic: Sigma,
  writer: Clapperboard,
  play: CirclePlay,
};
export default function ToolIcon({ name, ...props }) {
  const Icon = icons[name] || FileText;
  return <Icon size={20} strokeWidth={1.7} aria-hidden="true" {...props} />;
}
