#使用 deepwukong的数据创建一个公用的（sysevr, vuldeepecker, deeepecker）可以共同使用的dataset
#向量化方法deepwukong 使用 d2v， vdp 和 sys 使用 w2v

import os
import json
import random
import numpy as np
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from torch_geometric.data import DataLoader
import torch
from torch_geometric.data import Data
import shutil
#
# edge_index = torch.tensor([[0, 1],
#                            [2, 3],
#                            [4, 5],
#                            [6,7]
#                     ], dtype=torch.long)
# data = Data(edge_index=edge_index.t().contiguous())
from torch_geometric.data import DataLoader
# loader = DataLoader(data, batch_size=2, shuffle=True)
# for i in loader:
#     b = 1

import torch
from torch_geometric.data import InMemoryDataset
from gensim.test.utils import common_texts
from utils.json_ops import read_json
from utils.vectorize_gadget import GadgetVectorizer

# class DfTData(Data):
#     def __init__(self, x=None, edge_index=None,y=None, flip=None, xfg_id=None, pos = None, norm = None, face = None, edge_attr=None,  **kwargs):
#         super(DfTData, self).__init__(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y, pos=pos, norm=norm, face=face, **kwargs)
#         self.flip = flip 
#         self.xfg_id = xfg_id

class StackingDataset(InMemoryDataset):
    def __init__(self, config, data_json, transform=None, pre_transform=None):
        
        # self.key = key
        self.config = config
        # data_path = os.path.join(config.data_folder, config.name, config.dataset.name, f'{config.dataset.name}.json')
        geo_path = os.path.join(config.data_folder, config.name, 'geo')
        self.data_json = data_json
        self.d2v_path = os.path.join(config.data_folder, config.name, config.dataset.name,'d2v',
                         "d2v.model")
        self.w2v_path = os.path.join(config.data_folder, config.name, config.dataset.name,'w2v',
                         "w2v.model")
        if os.path.exists(geo_path) :
            shutil.rmtree(geo_path)
        super(StackingDataset, self).__init__(geo_path, transform, pre_transform)
        
        self.data, self.slices = torch.load(self.processed_paths[0])

    @property
    def raw_file_names(self):
        return ['some_file_1', 'some_file_2']
        # pass

    @property
    def processed_file_names(self):
        return ['data.pt']

    def download(self):
        # Download to `self.raw_dir`.
        pass

    def buildSensiXFGs(self):
        '''build Sensitive CFGs dict

        :param inputJsonDir:
        :return: {testcaseid:[{nodes:,nodes-vec:,edges:,target:},..]}
        '''
        SensiXFGs = list()

        d2v_model = Doc2Vec.load(self.d2v_path)
        vectorizer = GadgetVectorizer(self.config)

        vectorizer.load_model(w2v_path=self.w2v_path)
        # for doc in labeled_corpus:
        #     words = filter(lambda x: x in model.vocab, doc.words)
        
        for xfg in self.data_json:
            sensiXFG = dict()
            xfg_nodes = xfg["nodes-line-sym"]
            nodes_lineNo = xfg['nodes-lineNo']
            sensiXFG["nodes"] = xfg["nodes-line-sym"]
            sensiXFG["edges"] = xfg["edges-No"]
            sensiXFG["target"] = int(xfg["target"])
            sensiXFG["xfg_id"] = xfg['xfg_id']
            sensiXFG["flip"] = xfg['flip']
            nodeVecList = list()
            for nodeidx in range(len(xfg_nodes)):
                nodeVecList.append(d2v_model.docvecs[str(sensiXFG["xfg_id"]) + "_" + str(nodeidx)])
            sensiXFG["nodes-vec"] = nodeVecList
            
            
            zipped = zip(nodes_lineNo, xfg_nodes)
            sort_zipped = sorted(zipped,key=lambda x:(x[0]))
            nodes_line_sys_sorted = [node  for _, node in sort_zipped]
            vector, backwards_slice = vectorizer.vectorize2(nodes_line_sys_sorted)
            tokens_per_label = min(len(vector), self.config.hyper_parameters.seq_len)
            
            sensiXFG["backwards_slice"] = backwards_slice
            sensiXFG["tokens_per_label"] = tokens_per_label
            sensiXFG["gadget"] = vector[:tokens_per_label]
            SensiXFGs.append(sensiXFG)
            
        
        return SensiXFGs

    def process(self):
        # Read data into huge `Data` list.

        # data.x: Node feature matrix with shape [num_nodes, num_node_features]
        # data.edge_index: Graph connectivity in COO format with shape [2, num_edges] and type torch.long
        # data.edge_attr: Edge feature matrix with shape [num_edges, num_edge_features]
        # data.y: Target to train against (may have arbitrary shape)
        # data.pos: Node position matrix with shape [num_nodes, num_dimensions]

        print("START -- building sensitive CFGs Dict......")
        SensiXFGs = self.buildSensiXFGs()
        print("END -- building sensitive CFGs Dict!!!")


        # Read data into huge `Data` list.
        data_list = list()

        # TODO:解决样本不平衡的问题
        from imblearn.combine import SMOTETomek
        from imblearn.over_sampling import RandomOverSampler
        from collections import Counter

        # smote_tomek = RandomOverSampler(random_state=0)
        X = list()
        Y = list()
        X_0 = list()
        X_1 = list()
        for xfg in SensiXFGs:
            y = xfg["target"]
            if (y == 0):
                X_0.append(xfg)
            else:
                X_1.append(xfg)
        # num = abs(len(X_0) - len(X_1))
        # if (len(X_0) > len(X_1)):
        #     # 扩展x1
        #
        #     for i in range(num):
        #         X_1.append(random.choice(X_1))
        #
        # else:
        #     # 扩展x0
        #     for i in range(num):
        #         X_0.append(random.choice(X_0))

        X.extend(X_0)
        Y.extend(len(X_0) * [0])
        X.extend(X_1)
        Y.extend(len(X_1) * [1])

        # X_resampled, y_resampled = smote_tomek.fit_sample(X, Y)
        X_resampled, y_resampled = X,Y
        print("Samples distributions are follows:")
        print(sorted(Counter(y_resampled).items()))

        print("START -- building sensitive CFGs in pytorch_geometric DATA format......")
        # infoToData = dict()
        # for graphk in graphs:
        for curSensiCFG in X_resampled:
            # curGraph = graphs[graphk]
            # curGraph = curGraph[0]
            edge_index_v = curSensiCFG["edges"]

            x_v = curSensiCFG["nodes-vec"]
            gadget_v = curSensiCFG["gadget"]
            y = torch.tensor([curSensiCFG["target"]], dtype=torch.long)

            x = torch.tensor(x_v, dtype=torch.float)
            gadget = torch.tensor(gadget_v, dtype=torch.float32)
            backwards_slice = torch.tensor([curSensiCFG["backwards_slice"]], dtype=torch.bool)
            tokens_per_label = torch.tensor([curSensiCFG["tokens_per_label"]], dtype=torch.int64)
            if (len(edge_index_v) != 0):
                # consider each edge has the same attr
                # edge_attr = []
                # for i in range(len(edge_index_v)):
                #     edge_attr.append([1])
                # edge_attr = torch.tensor(edge_attr,dtype=torch.float)

                edge_index = torch.tensor(edge_index_v, dtype=torch.long)
                # data = Data(x=x, edge_index=edge_index.t().contiguous(), y=y,edge_attr=edge_attr)
                # data = Data(x=x, edge_index=edge_index.t().contiguous(), y=y)
                data = Data(x=x, edge_index=edge_index.t().contiguous(), y=y , 
                            gadgets = gadget, 
                            is_back = backwards_slice,
                            tokens_per_label = tokens_per_label,
                            flip = curSensiCFG['flip'], xfg_id= curSensiCFG['xfg_id'])

            else:
                # edge_attr = torch.tensor([], dtype=torch.float)
                edge_index = torch.tensor([], dtype=torch.long)
                # data = Data(edge_index=edge_index,x=x, y=y,edge_attr=edge_attr)
                # data = Data(edge_index=edge_index,x=x, y=y)
                data = Data(edge_index=edge_index,x=x, y=y,
                            gadgets = gadget, 
                            is_back = backwards_slice,
                            tokens_per_label = tokens_per_label,
                            flip = curSensiCFG['flip'], xfg_id= curSensiCFG['xfg_id'])

            # info = torch.tensor(curSensiCFG["info"], dtype=torch.long)
            # data.info = info
            ## infoToData[curSensiCFG["info"]] = data
            ## print(edge_index.t().contiguous())
            ## print(data)
            data_list.append(data)
        # random.shuffle(data_list)
        np.random.shuffle(data_list)
        # edge_index = torch.tensor([[0, 1],
        #                            [1,2]
        #                            ], dtype=torch.long)
        # y1 = torch.tensor([0], dtype=torch.long)
        # y2 = torch.tensor([1], dtype=torch.long)
        #
        # x = torch.tensor([[-1], [0], [1]], dtype=torch.float)
        # data1 = Data(x = x,edge_index=edge_index.t().contiguous(), y=y1)
        # data2 = Data(x=x,edge_index=edge_index.t().contiguous(), y=y2)
        #
        # data_list = [data1, data2, data1, data2]

        # edge_index = torch.tensor([[]
        #                            ], dtype=torch.long)
        # y1 = torch.tensor([0], dtype=torch.long)
        # y2 = torch.tensor([1], dtype=torch.long)
        #
        # x = torch.tensor([[-1]], dtype=torch.float)
        # data1 = Data(x=x, edge_index=edge_index.t().contiguous(), y=y1)
        # data2 = Data(x=x, edge_index=edge_index.t().contiguous(), y=y2)
        #
        # data_list = [data1, data2, data1, data2]

        # if self.pre_filter is not None:
        #     data_list [data for data in data_list if self.pre_filter(data)]
        #
        # if self.pre_transform is not None:
        #     data_list = [self.pre_transform(data) for data in data_list]

        data, slices = self.collate(data_list)
        print("END -- building sensitive CFGs in pytorch_geometric DATA format!!!")
        print("START -- saving sensitive CFGs in pytorch_geometric DATA format......")

        torch.save((data, slices), self.processed_paths[0])
        print("END -- saving sensitive CFGs in pytorch_geometric DATA format!!!")
        
    @staticmethod
    def pre_train(config):
        
        data_path = os.path.join(config.data_folder, config.name, config.dataset.name, f'{config.dataset.name}.json')
        data_json = read_json(data_path)
        d2v_path = os.path.join(config.data_folder, config.name, config.dataset.name,'d2v',
                         "d2v.model")
        w2v_path = os.path.join(config.data_folder, config.name, config.dataset.name,'w2v',
                         "w2v.model")
        vocab_path = os.path.join(config.data_folder, config.name,
                           config.dataset.name, 'w2v', "vocab.pkl") 
        if not os.path.exists(os.path.dirname(d2v_path)):
            os.makedirs(os.path.dirname(d2v_path))
        if not os.path.exists(os.path.dirname(w2v_path)):
            os.makedirs(os.path.dirname(w2v_path))
      
        #train d2v model
        documents = list()
        vectorizer = GadgetVectorizer(config)
        for idx, xfg in enumerate(data_json, start=0):
            xfg_id = xfg['xfg_id']
            xfg_nodes = xfg["nodes-line-sym"]  # 获取CFG结点的内容
            for node_idx in range(len(xfg_nodes)):  # 遍历每个CFG结点
                node = xfg_nodes[node_idx]  # 每个node的内容
                # print(node.split())ls
                # print([str(idx) + "_" + str(node_idx)])
                documents.append(
                        TaggedDocument(node.split(), [str(xfg_id) + "_" + str(node_idx)]))
            nodes_lineNo = xfg["nodes-lineNo"]
            zipped = zip(nodes_lineNo, xfg_nodes)
            sort_zipped = sorted(zipped,key=lambda x:(x[0]))
            nodes_line_sys_sorted = [node  for _, node in sort_zipped]
            vectorizer.add_gadget(nodes_line_sys_sorted)
        # print(documents)
        model = Doc2Vec(documents, vector_size=64, min_count=5, workers=8, window=8, dm=0, alpha=0.025,
                    epochs=50)
    
    
        print("START -- saving doc2vec model......")
        model.save(d2v_path)
        print("END -- saving doc2vec model......")
        
        #train w2v model
        print("START -- saving word2vec model......")
        vectorizer.train_model(w2v_path)
        vectorizer.build_vocab(vocab_path) 
        print("END -- saving word2vec model......")
        
        
        

# def main():
#     cwe_id = '79'
#     data_path = 'data/'
#     geno_path = 'data/{}/'.format(cwe_id)
#     dataset = PGDataset(data_path, geno_path, cwe_id)
#     print(dataset)
#     loader = DataLoader(dataset, batch_size=2, shuffle=True)
#     # for i in loader:
#     #     print(i)
#     edge_index = torch.tensor([[0, 1],
#                                ], dtype=torch.long)
#     y = torch.tensor([0], dtype=torch.long)
#     data1 = Data(edge_index=edge_index.t().contiguous(), y=y)
    
#     print(data1)

# if __name__ == '__main__':

    
#     main()
