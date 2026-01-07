import { useEffect, useState } from "react";
import { Plus, Edit, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ModifierGroupFormDialog } from "./ModifierGroupFormDialog";
import { ModifierGroup, Product } from "@/lib/api";

interface ModifierPanelProps {
  selectedProduct: Product | null;
  modifierGroups: ModifierGroup[];
  onModifierGroupsUpdated: () => Promise<void>;
}

export const ModifierPanel = ({
  selectedProduct,
  modifierGroups,
  onModifierGroupsUpdated,
}: ModifierPanelProps) => {
  const [assignedGroups, setAssignedGroups] = useState<number[]>([]);
  const [showAssignDialog, setShowAssignDialog] = useState(false);
  const [showGroupFormDialog, setShowGroupFormDialog] = useState(false);
  const [editingGroup, setEditingGroup] = useState<ModifierGroup | null>(null);
  const [selectedForAssign, setSelectedForAssign] = useState<number[]>([]);

  useEffect(() => {
    if (selectedProduct) {
      setAssignedGroups(selectedProduct.modifierGroups ?? []);
    }
  }, [selectedProduct]);

  const handleAssignGroups = () => {
    setAssignedGroups([...new Set([...assignedGroups, ...selectedForAssign])]);
    setShowAssignDialog(false);
    setSelectedForAssign([]);
  };

  const handleRemoveGroup = (groupId: number) => {
    setAssignedGroups(assignedGroups.filter(id => id !== groupId));
  };

  const handleNewGroup = () => {
    setEditingGroup(null);
    setShowGroupFormDialog(true);
  };

  const handleEditGroup = (group: ModifierGroup) => {
    setEditingGroup(group);
    setShowGroupFormDialog(true);
  };

  if (!selectedProduct) {
    return (
      <Card className="p-6 h-full flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <Settings className="h-16 w-16 mx-auto mb-3 opacity-50" />
          <p className="font-semibold">Selecciona un producto</p>
          <p className="text-sm mt-1">Haz clic en "Modificadores" para gestionar sus opciones</p>
        </div>
      </Card>
    );
  }

  const assignedGroupObjects = modifierGroups.filter(g =>
    assignedGroups.includes(g.id)
  );

  return (
    <div className="space-y-4">
      <Card className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-xl font-bold">{selectedProduct.name}</h3>
            <div className="flex gap-2 mt-2">
              <Badge variant="outline">{selectedProduct.category}</Badge>
              <Badge variant="default" className="bg-secondary">
                ${selectedProduct.price.toFixed(2)}
              </Badge>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold">Grupos de modificadores asignados</h4>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAssignDialog(true)}
            >
              <Plus className="h-4 w-4 mr-1" />
              Asignar grupo
            </Button>
          </div>

          {assignedGroupObjects.length === 0 ? (
            <div className="text-sm text-muted-foreground text-center py-4 border rounded-lg">
              No hay grupos asignados
            </div>
          ) : (
            <div className="space-y-2">
              {assignedGroupObjects.map((group) => (
                <div
                  key={group.id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div>
                    <div className="font-semibold">{group.name}</div>
                    <div className="text-sm text-muted-foreground">
                      Min: {group.minSelection} · Max: {group.maxSelection}
                      {group.required && " · Obligatorio"}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveGroup(group.id)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Modifier Groups Management */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-semibold">Grupos de modificadores</h4>
          <Button
            variant="default"
            size="sm"
            className="bg-secondary hover:bg-secondary/90"
            onClick={handleNewGroup}
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
              {modifierGroups.map((group) => (
                <TableRow key={group.id}>
                  <TableCell>
                    <div>
                      <div className="font-semibold">{group.name}</div>
                      {group.required && (
                        <Badge variant="destructive" className="text-xs mt-1">
                          Obligatorio
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm">
                    {group.minSelection} / {group.maxSelection}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{group.modifiers.length}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditGroup(group)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Trash2 className="h-4 w-4 text-danger" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Assign Group Dialog */}
      <Dialog open={showAssignDialog} onOpenChange={setShowAssignDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Asignar grupos de modificadores</DialogTitle>
            <DialogDescription>
              Selecciona los grupos que deseas asignar a {selectedProduct.name}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {modifierGroups.map((group) => (
              <div
                key={group.id}
                className="flex items-start space-x-3 p-3 border rounded-lg"
              >
                <Checkbox
                  id={`assign-${group.id}`}
                  checked={selectedForAssign.includes(group.id) || assignedGroups.includes(group.id)}
                  onCheckedChange={(checked) => {
                    if (checked && !assignedGroups.includes(group.id)) {
                      setSelectedForAssign([...selectedForAssign, group.id]);
                    } else {
                      setSelectedForAssign(selectedForAssign.filter(id => id !== group.id));
                    }
                  }}
                  disabled={assignedGroups.includes(group.id)}
                />
                <Label htmlFor={`assign-${group.id}`} className="flex-1 cursor-pointer">
                  <div className="font-semibold">{group.name}</div>
                  <div className="text-sm text-muted-foreground mt-1">
                    Min {group.minSelection} · Max {group.maxSelection}
                    {group.required && " · Obligatorio"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {group.modifiers.length} opciones disponibles
                  </div>
                </Label>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowAssignDialog(false)} className="flex-1">
              Cancelar
            </Button>
            <Button
              onClick={handleAssignGroups}
              className="flex-1"
              disabled={selectedForAssign.length === 0}
            >
              Confirmar
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Modifier Group Form Dialog */}
      <ModifierGroupFormDialog
        open={showGroupFormDialog}
        onOpenChange={setShowGroupFormDialog}
        editingGroup={editingGroup}
        onSaved={onModifierGroupsUpdated}
      />
    </div>
  );
};

// Settings icon import
import { Settings } from "lucide-react";
