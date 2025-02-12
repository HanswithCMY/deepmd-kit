# SPDX-License-Identifier: LGPL-3.0-or-later
from typing import (
    Any,
    Optional,
    Union,
)

import numpy as np

from deepmd.dpmodel.output_def import (
    FittingOutputDef,
    ModelOutputDef,
    OutputVariableDef,
)

from .deep_eval import (
    DeepEval,
)


class DeepDOS(DeepEval):
    """Deep density of states model.

    Parameters
    ----------
    model_file : Path
        The name of the frozen model file.
    *args : list
        Positional arguments.
    auto_batch_size : bool or int or AutoBatchSize, default: True
        If True, automatic batch size will be used. If int, it will be used
        as the initial batch size.
    neighbor_list : ase.neighborlist.NewPrimitiveNeighborList, optional
        The ASE neighbor list class to produce the neighbor list. If None, the
        neighbor list will be built natively in the model.
    **kwargs : dict
        Keyword arguments.
    """

    @property
    def output_def(self) -> ModelOutputDef:
        """Get the output definition of this model."""
        return ModelOutputDef(
            FittingOutputDef(
                [
                    OutputVariableDef(
                        "dos",
                        shape=[-1],
                        reducible=True,
                        atomic=True,
                    ),
                ]
            )
        )

    @property
    def numb_dos(self) -> int:
        """Get the number of DOS."""
        return self.get_numb_dos()

    def eval(
        self,
        coords: np.ndarray,
        cells: Optional[np.ndarray],
        atom_types: Union[list[int], np.ndarray],
        atomic: bool = False,
        fparam: Optional[np.ndarray] = None,
        aparam: Optional[np.ndarray] = None,
        mixed_type: bool = False,
        **kwargs: Any,
    ) -> tuple[np.ndarray, ...]:
        """Evaluate energy, force, and virial. If atomic is True,
        also return atomic energy and atomic virial.

        Parameters
        ----------
        coords : np.ndarray
            The coordinates of the atoms, in shape (nframes, natoms, 3).
        cells : np.ndarray
            The cell vectors of the system, in shape (nframes, 9). If the system
            is not periodic, set it to None.
        atom_types : list[int] or np.ndarray
            The types of the atoms. If mixed_type is False, the shape is (natoms,);
            otherwise, the shape is (nframes, natoms).
        atomic : bool, optional
            Whether to return atomic energy and atomic virial, by default False.
        fparam : np.ndarray, optional
            The frame parameters, by default None.
        aparam : np.ndarray, optional
            The atomic parameters, by default None.
        mixed_type : bool, optional
            Whether the atom_types is mixed type, by default False.
        **kwargs : dict[str, Any]
            Keyword arguments.

        Returns
        -------
        energy
            The energy of the system, in shape (nframes,).
        force
            The force of the system, in shape (nframes, natoms, 3).
        virial
            The virial of the system, in shape (nframes, 9).
        atomic_energy
            The atomic energy of the system, in shape (nframes, natoms). Only returned
            when atomic is True.
        atomic_virial
            The atomic virial of the system, in shape (nframes, natoms, 9). Only returned
            when atomic is True.
        """
        (
            coords,
            cells,
            atom_types,
            fparam,
            aparam,
            nframes,
            natoms,
        ) = self._standard_input(coords, cells, atom_types, fparam, aparam, mixed_type)
        results = self.deep_eval.eval(
            coords,
            cells,
            atom_types,
            atomic,
            fparam=fparam,
            aparam=aparam,
            **kwargs,
        )
        # energy = results["dos_redu"].reshape(nframes, self.get_numb_dos())
        atomic_energy = results["dos"].reshape(nframes, natoms, self.get_numb_dos())
        # not same as dos_redu... why?
        energy = np.sum(atomic_energy, axis=1)

        if atomic:
            return (
                energy,
                atomic_energy,
            )
        else:
            return (energy,)

    def get_numb_dos(self) -> int:
        return self.deep_eval.get_numb_dos()


__all__ = ["DeepDOS"]
