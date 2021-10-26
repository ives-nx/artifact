import pickle
from dataclasses import dataclass
from typing import List, Tuple

import numpy
from numpy.lib.function_base import flip
import joblib

@dataclass
class BufferedPathContext:
    """Class for storing buffered path contexts.

    :attr vectors: [total word len, embedding size]
    :attr labels: list [buffer size]
    :attr words_per_label: list [buffer size] -- number of words for each label

    """

    vectors: numpy.ndarray
    labels: List[int]
    words_per_label: List[int]
    idx: List[int]
    flip: List[bool]
    def __post_init__(self):
        self._end_idx = numpy.cumsum(self.words_per_label).tolist()
        self._start_idx = [0] + self._end_idx[:-1]

    def __len__(self):
        return len(self.words_per_label)

    def __getitem__(self, idx:int) -> Tuple[numpy.ndarray, int, bool, int]:
        if isinstance(idx, int):
            
            path_slice = slice(self._start_idx[idx], self._end_idx[idx])
            vector = self.vectors[path_slice, :]
            return vector, self.labels[idx], self.words_per_label[idx], self.idx[idx], self.flip[idx]
        elif isinstance(idx, list):
            vectors = []
            labels = []
            words_per_label = []
            indexs = []
            flip = []
            for i in idx:
                path_slice = slice(self._start_idx[i], self._end_idx[i])
                vector = self.vectors[path_slice, :]
                vectors.append(vector)
                labels.append(self.labels[i])
                indexs.append(self.idx[i])
                flip.append(self.flip[i])
                words_per_label.append(self.words_per_label[i])
            merge_vectors = numpy.concatenate(vectors, axis=0)
            return BufferedPathContext(merge_vectors, labels, words_per_label, indexs, flip)

    def dump(self, path: str):
        with open(path, "wb") as pickle_file:
            pickle.dump([self.vectors, self.labels,
                         self.words_per_label, self.idx, self.flip], pickle_file, protocol=pickle.HIGHEST_PROTOCOL)
            

    @staticmethod
    def load(path: str):
        with open(path, "rb") as pickle_file:
            data = pickle.load(pickle_file)
           
        if not isinstance(data, tuple) and len(data) != 5:
            raise RuntimeError("Incorrect data inside pickled file")
        return BufferedPathContext(*data)

    @staticmethod
    def create_from_lists(X: List[numpy.ndarray], labels: List[int]) -> "BufferedPathContext":
        vectors = []
        idx = []
        flip = []
        for data in X:
            vectors.append(data[0])
            idx.append(data[1])
            flip.append(data[2])
        merge_vectors = numpy.concatenate(vectors, axis=0)
        words_per_label = [len(vector) for vector in vectors]

        return BufferedPathContext(merge_vectors, labels,
                                   words_per_label, idx, flip)
    @staticmethod
    def create_from_dict(X: dict) -> "BufferedPathContext":
        vectors = X['vectors']
        labels = X['labels']
        words_per_label = X['words_per_label']
        idxs = X['idxs']
        flips = X['flips']
        merge_vectors = numpy.concatenate(vectors, axis=0)
        
        return BufferedPathContext(merge_vectors, labels,
                                   words_per_label, idxs, flips)
    @staticmethod
    def rm_samples(src_data ,rm_id_list:list):
        re_data = dict()
        vectors = []
        labels = []
        words_per_label = []
        idxs = []
        flips = []
        for data in src_data:
            i = int(data[3])
            label = data[1]
            if i in rm_id_list:
                # label = data[1] ^ 1
                continue
            vectors.append(data[0])
            labels.append(label)
            words_per_label.append(data[2])
            idxs.append(data[3])
            flips.append(data[4])
        re_data['vectors'] = vectors
        re_data['labels'] = labels
        re_data['words_per_label'] = words_per_label
        re_data['idxs'] = idxs
        re_data['flips'] = flips

        return BufferedPathContext.create_from_dict(re_data)
   
    @staticmethod
    def sysevr_downsample(src_data, ds_count):
        re_data = dict()
        size = len(src_data)
        a = numpy.arange(size)
        indices = numpy.random.choice(a, ds_count, replace=False)
        vectors = []
        labels = []
        words_per_label = []
        idxs = []
        flips = []
        ds_idx = []
        for i, data in enumerate(src_data):
            if i in indices:
                vectors.append(data[0])
                labels.append(data[1])
                words_per_label.append(data[2])
                idxs.append(data[3])
                ds_idx.append(data[3])
                flips.append(data[4])
        re_data['vectors'] = vectors
        re_data['labels'] = labels
        re_data['words_per_label'] = words_per_label
        re_data['idxs'] = idxs
        re_data['flips'] = flips

        return BufferedPathContext.create_from_dict(re_data), ds_idx   

    @staticmethod
    def get_loss_vector(ws, wds, dds):
        X_train = []
        Y_train = []
        flipped = []
        xfg_ids = []

        for xfg in ws:
            xfg_id = xfg['xfg_id']
            if str(xfg_id) in dds.keys():
                x = dds[str(xfg_id)]
                x.extend(wds[str(xfg_id)])
                # x = wds[str(xfg_id)]
                X_train.append(x)
                Y_train.append(xfg['val'])
                flipped.append(xfg['flip'])
                xfg_ids.append(xfg['xfg_id'])
        return X_train, Y_train, flipped ,xfg_ids

    @staticmethod
    def sys_rm_noisy_sample(ws, outlier_list):
        outlier_id = []
        for outlier in outlier_list:
            idx = int(outlier[0])
            outlier_id.append(idx)

        re_data = dict()
        vectors = []
        labels = []
        words_per_label = []
        idxs = []
        flips = []

        for data in ws:
            if data[3] in outlier_id:
                continue
            vectors.append(data[0])
            labels.append(data[1])
            words_per_label.append(data[2])
            idxs.append(data[3])
            flips.append(data[4])
        re_data['vectors'] = vectors
        re_data['labels'] = labels
        re_data['words_per_label'] = words_per_label
        re_data['idxs'] = idxs
        re_data['flips'] = flips

        return outlier_id, BufferedPathContext.create_from_dict(re_data)

    def joblib_dump(self, path:str):
        with open(path, "wb") as pickle_file:
            joblib.dump([self.vectors, self.labels,
                         self.words_per_label, self.idx, self.flip], pickle_file)
    @staticmethod
    def joblib_load(path:str):
        with open(path, "rb") as pickle_file:
            data = joblib.load(pickle_file)
           
        if not isinstance(data, tuple) and len(data) != 5:
            raise RuntimeError("Incorrect data inside pickled file")
        return BufferedPathContext(*data)