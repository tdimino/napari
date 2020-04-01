import itertools
from logging import getLogger
from typing import List, Optional, Sequence, Union
from os import fspath
import numpy as np

from .. import layers
from ..plugins.io import read_data_with_plugins
from ..utils import colormaps, io
from ..utils.misc import ensure_iterable, is_iterable

logger = getLogger(__name__)


class AddLayersMixin:
    """A mixin that adds add_* methods for adding layers to the ViewerModel.

    Each method corresponds to adding one or more layers to the viewer.
    Methods that just add a single layer contain the keyword arguments and
    copies of the documentation from that the layer. These are copied and
    pasted instead of being autogenerated because IDEs like PyCharm parse the
    source code for docs instead of pulling it up dynamically.

    These methods are separated into a mixin to keep the ViewerModel class
    easier to read and make these methods easier to maintain.
    """

    def add_layer(self, layer):
        """Add a layer to the viewer.

        Parameters
        ----------
        layer : napari.layers.Layer
            Layer to add.
        """
        layer.events.select.connect(self._update_active_layer)
        layer.events.deselect.connect(self._update_active_layer)
        layer.events.status.connect(self._update_status)
        layer.events.help.connect(self._update_help)
        layer.events.interactive.connect(self._update_interactive)
        layer.events.cursor.connect(self._update_cursor)
        layer.events.cursor_size.connect(self._update_cursor_size)
        layer.events.data.connect(self._on_layers_change)
        layer.dims.events.ndisplay.connect(self._on_layers_change)
        layer.dims.events.order.connect(self._on_layers_change)
        layer.dims.events.range.connect(self._on_layers_change)
        self.layers.append(layer)
        self._update_layers(layers=[layer])

        if len(self.layers) == 1:
            self.reset_view()

    def add_image(
        self,
        data=None,
        *,
        channel_axis=None,
        rgb=None,
        is_pyramid=None,
        colormap=None,
        contrast_limits=None,
        gamma=1,
        interpolation='nearest',
        rendering='mip',
        iso_threshold=0.5,
        attenuation=0.5,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=1,
        blending=None,
        visible=True,
        path=None,
    ) -> Union[layers.Image, List[layers.Image]]:
        """Add an image layer to the layers list.

        Parameters
        ----------
        data : array or list of array
            Image data. Can be N dimensional. If the last dimension has length
            3 or 4 can be interpreted as RGB or RGBA if rgb is `True`. If a
            list and arrays are decreasing in shape then the data is treated as
            an image pyramid.
        channel_axis : int, optional
            Axis to expand image along.
        rgb : bool
            Whether the image is rgb RGB or RGBA. If not specified by user and
            the last dimension of the data has length 3 or 4 it will be set as
            `True`. If `False` the image is interpreted as a luminance image.
        is_pyramid : bool
            Whether the data is an image pyramid or not. Pyramid data is
            represented by a list of array like image data. If not specified by
            the user and if the data is a list of arrays that decrease in shape
            then it will be taken to be a pyramid. The first image in the list
            should be the largest.
        colormap : str, vispy.Color.Colormap, tuple, dict, list
            Colormaps to use for luminance images. If a string must be the name
            of a supported colormap from vispy or matplotlib. If a tuple the
            first value must be a string to assign as a name to a colormap and
            the second item must be a Colormap. If a dict the key must be a
            string to assign as a name to a colormap and the value must be a
            Colormap. If a list then must be same length as the axis that is
            being expanded as channels, and each colormap is applied to each
            new image layer.
        contrast_limits : list (2,)
            Color limits to be used for determining the colormap bounds for
            luminance images. If not passed is calculated as the min and max of
            the image. If list of lists then must be same length as the axis
            that is being expanded and then each colormap is applied to each
            image.
        gamma : list, float
            Gamma correction for determining colormap linearity. Defaults to 1.
            If a list then must be same length as the axis that is being
            expanded and then each entry in the list is applied to each image.
        interpolation : str
            Interpolation mode used by vispy. Must be one of our supported
            modes.
        rendering : str
            Rendering mode used by vispy. Must be one of our supported
            modes.
        iso_threshold : float
            Threshold for isosurface.
        attenuation : float
            Attenuation rate for attenuated maximum intensity projection.
        name : str
            Name of the layer.
        metadata : dict
            Layer metadata.
        scale : tuple of float
            Scale factors for the layer.
        translate : tuple of float
            Translation values for the layer.
        opacity : float
            Opacity of the layer visual, between 0.0 and 1.0.
        blending : str
            One of a list of preset blending modes that determines how RGB and
            alpha values of the layer visual get mixed. Allowed values are
            {'opaque', 'translucent', and 'additive'}.
        visible : bool
            Whether the layer visual is currently being displayed.
        path : str or list of str
            Path or list of paths to image data. Paths can be passed as strings
            or `pathlib.Path` instances.

        Returns
        -------
        layer : :class:`napari.layers.Image` or list
            The newly-created image layer or list of image layers.
        """
        if data is None and path is None:
            raise ValueError("One of either data or path must be provided")
        elif data is not None and path is not None:
            raise ValueError("Only one of data or path can be provided")
        elif data is None:
            data = io.magic_imread(path)

        if channel_axis is None:
            if colormap is None:
                colormap = 'gray'
            if blending is None:
                blending = 'translucent'
            layer = layers.Image(
                data,
                rgb=rgb,
                is_pyramid=is_pyramid,
                colormap=colormap,
                contrast_limits=contrast_limits,
                gamma=gamma,
                interpolation=interpolation,
                rendering=rendering,
                iso_threshold=iso_threshold,
                attenuation=attenuation,
                name=name,
                metadata=metadata,
                scale=scale,
                translate=translate,
                opacity=opacity,
                blending=blending,
                visible=visible,
            )
            self.add_layer(layer)
            return layer
        else:
            if is_pyramid:
                n_channels = data[0].shape[channel_axis]
            else:
                n_channels = data.shape[channel_axis]

            name = ensure_iterable(name)

            if blending is None:
                blending = 'additive'

            if colormap is None:
                if n_channels < 3:
                    colormap = colormaps.MAGENTA_GREEN
                else:
                    colormap = itertools.cycle(colormaps.CYMRGB)
            else:
                colormap = ensure_iterable(colormap)

            # If one pair of clim values is passed then need to iterate them to
            # all layers.
            if contrast_limits is not None and not is_iterable(
                contrast_limits[0]
            ):
                contrast_limits = itertools.repeat(contrast_limits)
            else:
                contrast_limits = ensure_iterable(contrast_limits)

            gamma = ensure_iterable(gamma)

            layer_list = []
            zipped_args = zip(
                range(n_channels), colormap, contrast_limits, gamma, name
            )
            for i, cmap, clims, _gamma, name in zipped_args:
                if is_pyramid:
                    image = [
                        np.take(data[j], i, axis=channel_axis)
                        for j in range(len(data))
                    ]
                else:
                    image = np.take(data, i, axis=channel_axis)
                layer = layers.Image(
                    image,
                    rgb=rgb,
                    colormap=cmap,
                    contrast_limits=clims,
                    gamma=_gamma,
                    interpolation=interpolation,
                    rendering=rendering,
                    name=name,
                    metadata=metadata,
                    scale=scale,
                    translate=translate,
                    opacity=opacity,
                    blending=blending,
                    visible=visible,
                )
                self.add_layer(layer)
                layer_list.append(layer)
            return layer_list

    def add_points(
        self,
        data=None,
        *,
        properties=None,
        symbol='o',
        size=10,
        edge_width=1,
        edge_color='black',
        edge_color_cycle=None,
        edge_colormap='viridis',
        edge_contrast_limits=None,
        face_color='white',
        face_color_cycle=None,
        face_colormap='viridis',
        face_contrast_limits=None,
        n_dimensional=False,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=1,
        blending='translucent',
        visible=True,
    ) -> layers.Points:
        """Add a points layer to the layers list.

        Parameters
        ----------
        data : array (N, D)
            Coordinates for N points in D dimensions.
        properties : dict {str: array (N,)}, DataFrame
            Properties for each point. Each property should be an array of length N,
            where N is the number of points.
        symbol : str
            Symbol to be used for the point markers. Must be one of the
            following: arrow, clobber, cross, diamond, disc, hbar, ring,
            square, star, tailed_arrow, triangle_down, triangle_up, vbar, x.
        size : float, array
            Size of the point marker. If given as a scalar, all points are made
            the same size. If given as an array, size must be the same
            broadcastable to the same shape as the data.
        edge_width : float
            Width of the symbol edge in pixels.
        edge_color : str, array-like
            Color of the point marker border. Numeric color values should be RGB(A).
        edge_color_cycle : np.ndarray, list, cycle
            Cycle of colors (provided as RGBA) to map to edge_color if a
            categorical attribute is used to set face_color.
        edge_colormap : str, vispy.color.colormap.Colormap
            Colormap to set edge_color if a continuous attribute is used to set face_color.
            See vispy docs for details: http://vispy.org/color.html#vispy.color.Colormap
        edge_contrast_limits : None, (float, float)
            clims for mapping the property to a color map. These are the min and max value
            of the specified property that are mapped to 0 and 1, respectively.
            The default value is None. If set the none, the clims will be set to
            (property.min(), property.max())
        face_color : str, array-like
            Color of the point marker body. Numeric color values should be RGB(A).
        face_color_cycle : np.ndarray, list, cycle
            Cycle of colors (provided as RGBA) to map to face_color if a
            categorical attribute is used to set face_color.
        face_colormap : str, vispy.color.colormap.Colormap
            Colormap to set face_color if a continuous attribute is used to set face_color.
            See vispy docs for details: http://vispy.org/color.html#vispy.color.Colormap
        face_contrast_limits : None, (float, float)
            clims for mapping the property to a color map. These are the min and max value
            of the specified property that are mapped to 0 and 1, respectively.
            The default value is None. If set the none, the clims will be set to
            (property.min(), property.max())
        n_dimensional : bool
            If True, renders points not just in central plane but also in all
            n-dimensions according to specified point marker size.
        name : str
            Name of the layer.
        metadata : dict
            Layer metadata.
        scale : tuple of float
            Scale factors for the layer.
        translate : tuple of float
            Translation values for the layer.
        opacity : float
            Opacity of the layer visual, between 0.0 and 1.0.
        blending : str
            One of a list of preset blending modes that determines how RGB and
            alpha values of the layer visual get mixed. Allowed values are
            {'opaque', 'translucent', and 'additive'}.
        visible : bool
            Whether the layer visual is currently being displayed.

        Returns
        -------
        layer : :class:`napari.layers.Points`
            The newly-created points layer.

        Notes
        -----
        See vispy's marker visual docs for more details:
        http://api.vispy.org/en/latest/visuals.html#vispy.visuals.MarkersVisual
        """
        if data is None:
            ndim = max(self.dims.ndim, 2)
            data = np.empty([0, ndim])

        layer = layers.Points(
            data=data,
            properties=properties,
            symbol=symbol,
            size=size,
            edge_width=edge_width,
            edge_color=edge_color,
            edge_color_cycle=edge_color_cycle,
            edge_colormap=edge_colormap,
            edge_contrast_limits=edge_contrast_limits,
            face_color=face_color,
            face_color_cycle=face_color_cycle,
            face_colormap=face_colormap,
            face_contrast_limits=face_contrast_limits,
            n_dimensional=n_dimensional,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_labels(
        self,
        data=None,
        *,
        is_pyramid=None,
        num_colors=50,
        seed=0.5,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=0.7,
        blending='translucent',
        visible=True,
        path=None,
    ) -> layers.Labels:
        """Add a labels (or segmentation) layer to the layers list.

        An image-like layer where every pixel contains an integer ID
        corresponding to the region it belongs to.

        Using the viewer's label editing tools (painting, erasing) will
        modify the input-array in-place.

        To avoid this, pass a copy as follows:
            layer = viewer.add_labels(data.copy())
            # do some painting/editing

        Get the modified labels as follows:
            result = layer.data

        Parameters
        ----------
        data : array or list of array
            Labels data as an array or pyramid.
        is_pyramid : bool
            Whether the data is an image pyramid or not. Pyramid data is
            represented by a list of array like image data. If not specified by
            the user and if the data is a list of arrays that decrease in shape
            then it will be taken to be a pyramid. The first image in the list
            should be the largest.
        num_colors : int
            Number of unique colors to use in colormap.
        seed : float
            Seed for colormap random generator.
        name : str
            Name of the layer.
        metadata : dict
            Layer metadata.
        scale : tuple of float
            Scale factors for the layer.
        translate : tuple of float
            Translation values for the layer.
        opacity : float
            Opacity of the layer visual, between 0.0 and 1.0.
        blending : str
            One of a list of preset blending modes that determines how RGB and
            alpha values of the layer visual get mixed. Allowed values are
            {'opaque', 'translucent', and 'additive'}.
        visible : bool
            Whether the layer visual is currently being displayed.
        path : str or list of str
            Path or list of paths to image data. Paths can be passed as strings
            or `pathlib.Path` instances.

        Returns
        -------
        layer : :class:`napari.layers.Labels`
            The newly-created labels layer.
        """
        if data is None and path is None:
            raise ValueError("One of either data or path must be provided")
        elif data is not None and path is not None:
            raise ValueError("Only one of data or path can be provided")
        elif data is None:
            data = io.magic_imread(path)

        layer = layers.Labels(
            data,
            is_pyramid=is_pyramid,
            num_colors=num_colors,
            seed=seed,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_shapes(
        self,
        data=None,
        *,
        shape_type='rectangle',
        edge_width=1,
        edge_color='black',
        face_color='white',
        z_index=0,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=0.7,
        blending='translucent',
        visible=True,
    ) -> layers.Shapes:
        """Add a shapes layer to the layers list.

        Parameters
        ----------
        data : list or array
            List of shape data, where each element is an (N, D) array of the
            N vertices of a shape in D dimensions. Can be an 3-dimensional
            array if each shape has the same number of vertices.
        shape_type : string or list
            String of shape shape_type, must be one of "{'line', 'rectangle',
            'ellipse', 'path', 'polygon'}". If a list is supplied it must be
            the same length as the length of `data` and each element will be
            applied to each shape otherwise the same value will be used for all
            shapes.
        edge_width : float or list
            Thickness of lines and edges. If a list is supplied it must be the
            same length as the length of `data` and each element will be
            applied to each shape otherwise the same value will be used for all
            shapes.
        edge_color : str or list
            If string can be any color name recognized by vispy or hex value if
            starting with `#`. If array-like must be 1-dimensional array with 3
            or 4 elements. If a list is supplied it must be the same length as
            the length of `data` and each element will be applied to each shape
            otherwise the same value will be used for all shapes.
        face_color : str or list
            If string can be any color name recognized by vispy or hex value if
            starting with `#`. If array-like must be 1-dimensional array with 3
            or 4 elements. If a list is supplied it must be the same length as
            the length of `data` and each element will be applied to each shape
            otherwise the same value will be used for all shapes.
        z_index : int or list
            Specifier of z order priority. Shapes with higher z order are
            displayed ontop of others. If a list is supplied it must be the
            same length as the length of `data` and each element will be
            applied to each shape otherwise the same value will be used for all
            shapes.
        name : str
            Name of the layer.
        metadata : dict
            Layer metadata.
        scale : tuple of float
            Scale factors for the layer.
        translate : tuple of float
            Translation values for the layer.
        opacity : float or list
            Opacity of the layer visual, between 0.0 and 1.0.
        blending : str
            One of a list of preset blending modes that determines how RGB and
            alpha values of the layer visual get mixed. Allowed values are
            {'opaque', 'translucent', and 'additive'}.
        visible : bool
            Whether the layer visual is currently being displayed.

        Returns
        -------
        layer : :class:`napari.layers.Shapes`
            The newly-created shapes layer.
        """
        if data is None:
            ndim = max(self.dims.ndim, 2)
            data = np.empty((0, 0, ndim))

        layer = layers.Shapes(
            data=data,
            shape_type=shape_type,
            edge_width=edge_width,
            edge_color=edge_color,
            face_color=face_color,
            z_index=z_index,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_surface(
        self,
        data,
        *,
        colormap='gray',
        contrast_limits=None,
        gamma=1,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=1,
        blending='translucent',
        visible=True,
    ) -> layers.Surface:
        """Add a surface layer to the layers list.

        Parameters
        ----------
        data : 3-tuple of array
            The first element of the tuple is an (N, D) array of vertices of
            mesh triangles. The second is an (M, 3) array of int of indices
            of the mesh triangles. The third element is the (K0, ..., KL, N)
            array of values used to color vertices where the additional L
            dimensions are used to color the same mesh with different values.
        colormap : str, vispy.Color.Colormap, tuple, dict
            Colormap to use for luminance images. If a string must be the name
            of a supported colormap from vispy or matplotlib. If a tuple the
            first value must be a string to assign as a name to a colormap and
            the second item must be a Colormap. If a dict the key must be a
            string to assign as a name to a colormap and the value must be a
            Colormap.
        contrast_limits : list (2,)
            Color limits to be used for determining the colormap bounds for
            luminance images. If not passed is calculated as the min and max of
            the image.
        gamma : float
            Gamma correction for determining colormap linearity. Defaults to 1.
        name : str
            Name of the layer.
        metadata : dict
            Layer metadata.
        scale : tuple of float
            Scale factors for the layer.
        translate : tuple of float
            Translation values for the layer.
        opacity : float
            Opacity of the layer visual, between 0.0 and 1.0.
        blending : str
            One of a list of preset blending modes that determines how RGB and
            alpha values of the layer visual get mixed. Allowed values are
            {'opaque', 'translucent', and 'additive'}.
        visible : bool
            Whether the layer visual is currently being displayed.

        Returns
        -------
        layer : :class:`napari.layers.Surface`
            The newly-created surface layer.
        """
        layer = layers.Surface(
            data,
            colormap=colormap,
            contrast_limits=contrast_limits,
            gamma=gamma,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_vectors(
        self,
        data,
        *,
        edge_width=1,
        edge_color='red',
        length=1,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=0.7,
        blending='translucent',
        visible=True,
    ) -> layers.Vectors:
        """Add a vectors layer to the layers list.

        Parameters
        ----------
        data : (N, 2, D) or (N1, N2, ..., ND, D) array
            An (N, 2, D) array is interpreted as "coordinate-like" data and a
            list of N vectors with start point and projections of the vector in
            D dimensions. An (N1, N2, ..., ND, D) array is interpreted as
            "image-like" data where there is a length D vector of the
            projections at each pixel.
        edge_width : float
            Width for all vectors in pixels.
        length : float
             Multiplicative factor on projections for length of all vectors.
        edge_color : str
            Edge color of all the vectors.
        name : str
            Name of the layer.
        metadata : dict
            Layer metadata.
        scale : tuple of float
            Scale factors for the layer.
        translate : tuple of float
            Translation values for the layer.
        opacity : float
            Opacity of the layer visual, between 0.0 and 1.0.
        blending : str
            One of a list of preset blending modes that determines how RGB and
            alpha values of the layer visual get mixed. Allowed values are
            {'opaque', 'translucent', and 'additive'}.
        visible : bool
            Whether the layer visual is currently being displayed.

        Returns
        -------
        layer : :class:`napari.layers.Vectors`
            The newly-created vectors layer.
        """
        layer = layers.Vectors(
            data,
            edge_width=edge_width,
            edge_color=edge_color,
            length=length,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_path(
        self, path: Union[str, Sequence[str]], stack: bool = False
    ) -> List[layers.Layer]:
        """Add a path or list of paths to the viewer.

        A list of paths will be handed one-by-one to the napari_get_reader hook
        if stack is False, otherwise the full list is passed to each plugin
        hook.

        Parameters
        ----------
        path : str or list of str
            A filepath, directory, or URL (or a list of any) to open.
        stack : bool, optional
            If a list of strings is passed and ``stack`` is ``True``, then the
            entire list will be passed to plugins.  It is then up to individual
            plugins to know how to handle a list of paths.  If ``stack`` is
            ``False``, then the ``path`` list is broken up and passed to plugin
            readers one by one.  by default False.

        Returns
        -------
        layers : list
            A list of any layers that were added to the viewer.
        """
        paths = [path] if isinstance(path, str) else path
        paths = [fspath(path) for path in paths]  # PathObjects -> str
        if not isinstance(paths, (tuple, list)):
            raise ValueError(
                "'path' argument must be a string, list, or tuple"
            )

        if stack:
            return self._add_layers_with_plugins(paths)

        added: List[layers.Layer] = []  # for layers that get added
        for _path in paths:
            added.extend(self._add_layers_with_plugins(_path))

        return added

    def _add_layers_with_plugins(
        self, path_or_paths: Union[str, Sequence[str]]
    ) -> List[layers.Layer]:
        """Load a path or a list of paths into the viewer using plugins.

        This function is mostly called from self.add_path, where the ``stack``
        argument determines whether a list of strings is handed to plugins one
        at a time, or en-masse.

        Parameters
        ----------
        path_or_paths : str or list of str
            A filepath, directory, or URL (or a list of any) to open. If a
            list, the assumption is that the list is to be treated as a stack.

        Returns
        -------
        List[layers.Layer]
            A list of any layers that were added to the viewer.
        """
        layer_data = read_data_with_plugins(path_or_paths)

        if not layer_data:
            # if layer_data is empty, it means no plugin could read path
            # we just want to provide some useful feedback, which includes
            # whether or not paths were passed to plugins as a list.
            if isinstance(path_or_paths, (tuple, list)):
                path_repr = f"[{path_or_paths[0]}, ...] as stack"
            else:
                path_repr = path_or_paths
            msg = f'No plugin found capable of reading {path_repr}.'
            logger.error(msg)
            return []

        # add each layer to the viewer
        added: List[layers.Layer] = []  # for layers that get added
        for data in layer_data:
            new = self._add_layer_from_data(*data)
            # some add_* methods return a List[Layer] others just a Layer
            # we want to always return a list
            added.extend(new if isinstance(new, list) else [new])
        return added

    def _add_layer_from_data(
        self, data, meta: dict = None, layer_type: Optional[str] = None
    ) -> Union[layers.Layer, List[layers.Layer]]:
        """Add arbitrary layer data to the viewer.

        Primarily intended for usage by reader plugin hooks.

        Parameters
        ----------
        data : Any
            Data in a format that is valid for the corresponding `add_*` method
            of the specified ``layer_type``.
        meta : dict, optional
            Dict of keyword arguments that will be passed to the corresponding
            `add_*` method.  MUST NOT contain any keyword arguments that are
            not valid for the corresponding method.
        layer_type : str
            Type of layer to add.  MUST have a corresponding add_* method on
            on the viewer instance.  If not provided, the layer is assumed to
            be "image", unless data.dtype is one of (np.int32, np.uint32,
            np.int64, np.uint64), in which case it is assumed to be "labels".

        Raises
        ------
        ValueError
            If ``layer_type`` is not one of the recognized layer types.
        TypeError
            If any keyword arguments in ``meta`` are unexpected for the
            corresponding `add_*` method for this layer_type.

        Examples
        --------
        A typical use case might be to upack a tuple of layer data with a
        specified layer_type.

        >>> viewer = napari.Viewer()
        >>> data = (
        ...     np.random.random((10, 2)) * 20,
        ...     {'face_color': 'blue'},
        ...     'points',
        ... )
        >>> viewer._add_layer_from_data(*data)

        """

        layer_type = (layer_type or '').lower()

        # assumes that big integer type arrays are likely labels.
        if not layer_type:
            if hasattr(data, 'dtype') and data.dtype in (
                np.int32,
                np.uint32,
                np.int64,
                np.uint64,
            ):
                layer_type = 'labels'
            else:
                layer_type = 'image'

        if layer_type not in layers.NAMES:
            raise ValueError(
                f"Unrecognized layer_type: '{layer_type}'. "
                f"Must be one of: {layers.NAMES}."
            )

        try:
            add_method = getattr(self, 'add_' + layer_type)
        except AttributeError:
            raise NotImplementedError(
                f"Sorry! {layer_type} is a valid layer type, but there is no "
                f"viewer.add_{layer_type} available yet."
            )

        try:
            layer = add_method(data, **(meta or {}))
        except TypeError as exc:
            if 'unexpected keyword argument' in str(exc):
                bad_key = str(exc).split('keyword argument ')[-1]
                raise TypeError(
                    "_add_layer_from_data received an unexpected keyword "
                    f"argument ({bad_key}) for layer type {layer_type}"
                ) from exc
            else:
                raise exc

        return layer