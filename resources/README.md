# 固定词法资源

W1/W2 使用以下固定资源：

- NLTK `3.9.2` 的 `averaged_perceptron_tagger_eng`。
- WordNet `3.0` lemmatizer 数据。
- Ghent University 发布的 SUBTLEX-US PoS/Zipf 表（2013 文件）。

安装依赖并生成本地资源：

```bash
python3 -m pip install -r requirements.txt
python3 scripts/setup_lexical_resources.py
```

安装脚本会校验三个官方 ZIP 的 SHA-256、SUBTLEX-US 表头和 74,286 条词形，随后生成：

```text
resources/
├── lexical_manifest.json
├── subtlex_us_zipf.tsv
└── nltk_data/
    ├── corpora/wordnet/
    └── taggers/averaged_perceptron_tagger_eng/
```

生成物不会进入 Git。需要把资源放在其他目录时，可以在安装和运行阶段分别设置：

```bash
python3 scripts/setup_lexical_resources.py --resource-dir /path/to/resources
export PRELABELING_RESOURCE_DIR=/path/to/resources
```

SUBTLEX-US 官方说明与下载页面：

- <https://www.ugent.be/plone_portal/pp/experimentele-psychologie/en/research/documents/subtlexus/overview.htm>

原始 SUBTLEX-US 数据由其权利人提供用于研究；本仓库只提交下载与校验脚本，不重新分发原始或转换后的数据。
