# SPDX-License-Identifier: LGPL-3.0-or-later
import logging
from typing import (
    Callable,
    Optional,
    Union,
)

import torch

from deepmd.dpmodel import (
    FittingOutputDef,
    OutputVariableDef,
)
from deepmd.pt.model.task.fitting import (
    GeneralFitting,
)
from deepmd.pt.utils import (
    env,
)
from deepmd.pt.utils.env import (
    DEFAULT_PRECISION,
)
from deepmd.utils.path import (
    DPPath,
)
from deepmd.utils.version import (
    check_version_compatibility,
)

log = logging.getLogger(__name__)


@GeneralFitting.register("dipole")
class DipoleFittingNet(GeneralFitting):
    """Construct a dipole fitting net.

    Parameters
    ----------
    ntypes : int
        Element count.
    dim_descrpt : int
        Embedding width per atom.
    embedding_width : int
        The dimension of rotation matrix, m1.
    neuron : list[int]
        Number of neurons in each hidden layers of the fitting net.
    resnet_dt : bool
        Using time-step in the ResNet construction.
    numb_fparam : int
        Number of frame parameters.
    numb_aparam : int
        Number of atomic parameters.
    activation_function : str
        Activation function.
    precision : str
        Numerical precision.
    mixed_types : bool
        If true, use a uniform fitting net for all atom types, otherwise use
        different fitting nets for different atom types.
    rcond : float, optional
        The condition number for the regression of atomic energy.
    seed : int, optional
        Random seed.
    r_differentiable
        If the variable is differentiated with respect to coordinates of atoms.
        Only reducible variable are differentiable.
    c_differentiable
        If the variable is differentiated with respect to the cell tensor (pbc case).
        Only reducible variable are differentiable.
    type_map: list[str], Optional
        A list of strings. Give the name to each type of atoms.
    """

    def __init__(
        self,
        ntypes: int,
        dim_descrpt: int,
        embedding_width: int,
        neuron: list[int] = [128, 128, 128],
        resnet_dt: bool = True,
        numb_fparam: int = 0,
        numb_aparam: int = 0,
        activation_function: str = "tanh",
        precision: str = DEFAULT_PRECISION,
        mixed_types: bool = True,
        rcond: Optional[float] = None,
        seed: Optional[Union[int, list[int]]] = None,
        exclude_types: list[int] = [],
        r_differentiable: bool = True,
        c_differentiable: bool = True,
        type_map: Optional[list[str]] = None,
        **kwargs,
    ) -> None:
        self.embedding_width = embedding_width
        self.r_differentiable = r_differentiable
        self.c_differentiable = c_differentiable
        super().__init__(
            var_name="dipole",
            ntypes=ntypes,
            dim_descrpt=dim_descrpt,
            neuron=neuron,
            resnet_dt=resnet_dt,
            numb_fparam=numb_fparam,
            numb_aparam=numb_aparam,
            activation_function=activation_function,
            precision=precision,
            mixed_types=mixed_types,
            rcond=rcond,
            seed=seed,
            exclude_types=exclude_types,
            type_map=type_map,
            **kwargs,
        )

    def _net_out_dim(self):
        """Set the FittingNet output dim."""
        return self.embedding_width

    def serialize(self) -> dict:
        data = super().serialize()
        data["type"] = "dipole"
        data["embedding_width"] = self.embedding_width
        data["r_differentiable"] = self.r_differentiable
        data["c_differentiable"] = self.c_differentiable
        return data

    @classmethod
    def deserialize(cls, data: dict) -> "GeneralFitting":
        data = data.copy()
        check_version_compatibility(data.pop("@version", 1), 2, 1)
        data.pop("var_name", None)
        return super().deserialize(data)

    def output_def(self) -> FittingOutputDef:
        return FittingOutputDef(
            [
                OutputVariableDef(
                    self.var_name,
                    [3],
                    reducible=True,
                    r_differentiable=self.r_differentiable,
                    c_differentiable=self.c_differentiable,
                ),
            ]
        )

    def compute_output_stats(
        self,
        merged: Union[Callable[[], list[dict]], list[dict]],
        stat_file_path: Optional[DPPath] = None,
    ) -> None:
        """
        Compute the output statistics (e.g. energy bias) for the fitting net from packed data.

        Parameters
        ----------
        merged : Union[Callable[[], list[dict]], list[dict]]
            - list[dict]: A list of data samples from various data systems.
                Each element, `merged[i]`, is a data dictionary containing `keys`: `torch.Tensor`
                originating from the `i`-th data system.
            - Callable[[], list[dict]]: A lazy function that returns data samples in the above format
                only when needed. Since the sampling process can be slow and memory-intensive,
                the lazy function helps by only sampling once.
        stat_file_path : Optional[DPPath]
            The path to the stat file.

        """
        pass

    def forward(
        self,
        descriptor: torch.Tensor,
        atype: torch.Tensor,
        gr: Optional[torch.Tensor] = None,
        g2: Optional[torch.Tensor] = None,
        h2: Optional[torch.Tensor] = None,
        fparam: Optional[torch.Tensor] = None,
        aparam: Optional[torch.Tensor] = None,
    ):
        nframes, nloc, _ = descriptor.shape
        assert gr is not None, "Must provide the rotation matrix for dipole fitting."
        # cast the input to internal precsion
        gr = gr.to(self.prec)
        # (nframes, nloc, m1)
        out = self._forward_common(descriptor, atype, gr, g2, h2, fparam, aparam)[
            self.var_name
        ]
        # (nframes * nloc, 1, m1)
        out = out.view(-1, 1, self.embedding_width)
        # (nframes * nloc, m1, 3)
        gr = gr.view(nframes * nloc, self.embedding_width, 3)
        # (nframes, nloc, 3)
        out = torch.bmm(out, gr).squeeze(-2).view(nframes, nloc, 3)
        return {self.var_name: out.to(env.GLOBAL_PT_FLOAT_PRECISION)}

    # make jit happy with torch 2.0.0
    exclude_types: list[int]
