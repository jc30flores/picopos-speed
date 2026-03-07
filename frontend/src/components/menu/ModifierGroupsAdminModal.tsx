import { useMemo, useState } from "react";
import { Edit, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ModifierGroup, deleteModifierGroup } from "@/lib/api";
import { ModifierGroupFormDialog } from "./ModifierGroupFormDialog";
import { toast } from "sonner";

interface ModifierGroupsAdminModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  modifierGroups: ModifierGroup[];
  onUpdated: () => Promise<void>;
}

export const ModifierGroupsAdminModal = ({ open, onOpenChange, modifierGroups, onUpdated }: ModifierGroupsAdminModalProps) => {
  const [groupSearch, setGroupSearch] = useState("");
  const [showGroupFormDialog, setShowGroupFormDialog] = useState(false);
  const [editingGroup, setEditingGroup] = useState<ModifierGroup | null>(null);
  const [groupToDelete, setGroupToDelete] = useState<ModifierGroup | null>(null);

  const filteredModifierGroups = useMemo(() => modifierGroups.filter((group) =>
    group.name.toLowerCase().includes(groupSearch.toLowerCase())
  ), [modifierGroups, groupSearch]);

  const handleDeleteGroup = async () => {
    if (!groupToDelete) return;
    try {
      await deleteModifierGroup(groupToDelete.id);
      await onUpdated();
      toast.success("Grupo eliminado correctamente");
      setGroupToDelete(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "No se pudo eliminar el grupo");
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Grupos de modificadores</DialogTitle>
            <DialogDescription>
              Administra el catálogo global de grupos y sus opciones.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Input
                placeholder="Buscar grupo…"
                value={groupSearch}
                onChange={(event) => setGroupSearch(event.target.value)}
              />
              <Button
                className="bg-secondary hover:bg-secondary/90"
                onClick={() => {
                  setEditingGroup(null);
                  setShowGroupFormDialog(true);
                }}
              >
                <Plus className="h-4 w-4 mr-1" />
                Nuevo grupo
              </Button>
            </div>

            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nombre</TableHead>
                    <TableHead>Min/Max</TableHead>
                    <TableHead>Opciones</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredModifierGroups.map((group) => (
                    <TableRow key={group.id}>
                      <TableCell>
                        <div>
                          <div className="font-semibold">{group.name}</div>
                          {group.required && (
                            <Badge variant="destructive" className="mt-1 text-xs">Obligatorio</Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">{group.minSelection} / {group.maxSelection}</TableCell>
                      <TableCell><Badge variant="outline">{group.modifiers.length}</Badge></TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="icon" onClick={() => { setEditingGroup(group); setShowGroupFormDialog(true); }}>
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setGroupToDelete(group)}>
                            <Trash2 className="h-4 w-4 text-danger" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {filteredModifierGroups.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-sm text-muted-foreground">
                        No hay grupos para mostrar.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(groupToDelete)} onOpenChange={(nextOpen) => !nextOpen && setGroupToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar grupo</DialogTitle>
            <DialogDescription>
              ¿Seguro que deseas eliminar el grupo {groupToDelete?.name}? Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => setGroupToDelete(null)}>Cancelar</Button>
            <Button variant="destructive" className="flex-1" onClick={handleDeleteGroup}>Eliminar</Button>
          </div>
        </DialogContent>
      </Dialog>

      <ModifierGroupFormDialog
        open={showGroupFormDialog}
        onOpenChange={setShowGroupFormDialog}
        editingGroup={editingGroup}
        onSaved={onUpdated}
      />
    </>
  );
};
