import os
from typing import Callable, List, Optional, Union
import inspect
from pathlib import Path
import tempfile

import PIL, cv2
import numpy as np

from pixeltable.type_system import StringType, IntType, JsonType, ColumnType, FloatType, ImageType, VideoType
from pixeltable.function import Function, FunctionRegistry
from pixeltable import catalog
from pixeltable import exprs
import pixeltable.exceptions as exc
# import all standard function modules here so they get registered with the FunctionRegistry
import pixeltable.functions.pil
import pixeltable.functions.pil.image
from pixeltable.utils.video import convert_to_h264


# def udf_call(eval_fn: Callable, return_type: ColumnType, tbl: Optional[catalog.Table]) -> exprs.FunctionCall:
#     """
#     Interprets eval_fn's parameters to be references to columns in 'tbl' and construct ColumnRefs as args.
#     """
#     params = inspect.signature(eval_fn).parameters
#     if len(params) > 0 and tbl is None:
#         raise exc.Error(f'udf_call() is missing tbl parameter')
#     args: List[exprs.ColumnRef] = []
#     for param_name in params:
#         if param_name not in tbl.cols_by_name:
#             raise exc.Error(
#                 (f'udf_call(): lambda argument names need to be valid column names in table {tbl.name}: '
#                  f'column {param_name} unknown'))
#         args.append(exprs.ColumnRef(tbl.cols_by_name[param_name]))
#     fn = Function.make_function(return_type, [arg.col_type for arg in args], eval_fn)
#     return exprs.FunctionCall(fn, args)

def cast(expr: exprs.Expr, target_type: ColumnType) -> exprs.Expr:
    expr.col_type = target_type
    return expr

dict_map = Function.make_function(IntType(), [StringType(), JsonType()], lambda s, d: d[s])


class SumAggregator:
    def __init__(self):
        self.sum: Union[int, float] = 0
    @classmethod
    def make_aggregator(cls) -> 'SumAggregator':
        return cls()
    def update(self, val: Union[int, float]) -> None:
        if val is not None:
            self.sum += val
    def value(self) -> Union[int, float]:
        return self.sum

sum = Function.make_library_aggregate_function(
    IntType(), [IntType()],
    'pixeltable.functions', 'SumAggregator.make_aggregator', 'SumAggregator.update', 'SumAggregator.value',
    allows_std_agg=True, allows_window=True)
FunctionRegistry.get().register_function(__name__, 'sum', sum)

class CountAggregator:
    def __init__(self):
        self.count = 0
    @classmethod
    def make_aggregator(cls) -> 'CountAggregator':
        return cls()
    def update(self, val: int) -> None:
        if val is not None:
            self.count += 1
    def value(self) -> int:
        return self.count

count = Function.make_library_aggregate_function(
    IntType(), [IntType()],
    'pixeltable.functions', 'CountAggregator.make_aggregator', 'CountAggregator.update', 'CountAggregator.value',
    allows_std_agg = True, allows_window = True)
FunctionRegistry.get().register_function(__name__, 'count', count)

class MeanAggregator:
    def __init__(self):
        self.sum = 0
        self.count = 0
    @classmethod
    def make_aggregator(cls) -> 'MeanAggregator':
        return cls()
    def update(self, val: int) -> None:
        if val is not None:
            self.sum += val
            self.count += 1
    def value(self) -> float:
        if self.count == 0:
            return None
        return self.sum / self.count

mean = Function.make_library_aggregate_function(
    FloatType(), [IntType()],
    'pixeltable.functions', 'MeanAggregator.make_aggregator', 'MeanAggregator.update', 'MeanAggregator.value',
    allows_std_agg = True, allows_window = True)
FunctionRegistry.get().register_function(__name__, 'mean', mean)

class VideoAggregator:
    def __init__(self):
        self.video_writer = None
        self.size = None

    @classmethod
    def make_aggregator(cls) -> 'VideoAggregator':
        return cls()

    def update(self, frame: PIL.Image.Image) -> None:
        if self.video_writer is None:
            self.size = (frame.width, frame.height)
            self.out_file = Path(os.getcwd()) / f'{Path(tempfile.mktemp()).name}.mp4'
            self.tmp_file = Path(os.getcwd()) / f'{Path(tempfile.mktemp()).name}.mp4'
            # our target codec is H.264, but it's tainted by GPL and cv2 doesn't include it, so we use MP4V instead
            self.video_writer = cv2.VideoWriter(str(self.tmp_file), cv2.VideoWriter_fourcc(*'mp4v'), 25, self.size)

        frame_array = np.array(frame)
        frame_array = cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)
        self.video_writer.write(frame_array)

    def value(self) -> str:
        self.video_writer.release()
        convert_to_h264(self.tmp_file, self.out_file)
        os.remove(self.tmp_file)
        return str(self.out_file)

make_video = Function.make_library_aggregate_function(
    VideoType(), [ImageType()],  # params: frame
    module_name = 'pixeltable.functions',
    init_symbol = 'VideoAggregator.make_aggregator',
    update_symbol = 'VideoAggregator.update',
    value_symbol = 'VideoAggregator.value',
    requires_order_by=True, allows_std_agg=True, allows_window=False)
FunctionRegistry.get().register_function(__name__, 'make_video', make_video)

__all__ = [
    #udf_call,
    cast,
    dict_map,
    sum,
    count,
    mean,
    make_video
]
