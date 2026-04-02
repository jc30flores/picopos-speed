import { Button } from "@/components/ui/button";
import { LayoutGrid } from "lucide-react";
import { useNavigate } from "react-router-dom";

export const Navigation = () => {
  const navigate = useNavigate();
  return (
    <Button
      type="button"
      size="icon"
      variant="outline"
      className="fixed left-3 top-3 z-50 h-12 w-12 rounded-full bg-background/95 shadow-md"
      onClick={() => navigate("/")}
      aria-label="Menú principal"
      title="Menú principal"
    >
      <LayoutGrid className="h-5 w-5" />
    </Button>
  );
};
