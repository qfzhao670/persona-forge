# 固定词法资源

W1/W2/G1 使用以下固定资源：

- NLTK `3.9.2` 的 `averaged_perceptron_tagger_eng`。
- WordNet `3.0` lemmatizer 数据。
- Ghent University 发布的 SUBTLEX-US PoS/Zipf 表（2013 文件）。
- 仓库内的 `function_words_v1.json`：项目编写的八类英语功能词清单，共 364 个唯一词形、429 个类别成员关系。

安装依赖并生成本地资源：

```bash
python3 -m pip install -r requirements.txt
python3 scripts/setup_lexical_resources.py
```

安装脚本会校验三个官方 ZIP 的 SHA-256、SUBTLEX-US 表头和 74,286 条词形，随后生成：

```text
resources/
├── function_words_v1.json
├── lexical_manifest.json
├── subtlex_us_zipf.tsv
└── nltk_data/
    ├── corpora/wordnet/
    └── taggers/averaged_perceptron_tagger_eng/
```

`function_words_v1.json` 会进入 Git；下载得到的 SUBTLEX-US、NLTK 数据和生成的 manifest 不会进入 Git。需要把资源放在其他目录时，安装脚本会自动复制固定功能词词典，可以在安装和运行阶段分别设置：

```bash
python3 scripts/setup_lexical_resources.py --resource-dir /path/to/resources
export PRELABELING_RESOURCE_DIR=/path/to/resources
```

SUBTLEX-US 官方说明与下载页面：

- <https://www.ugent.be/plone_portal/pp/experimentele-psychologie/en/research/documents/subtlexus/overview.htm>

原始 SUBTLEX-US 数据由其权利人提供用于研究；本仓库只提交下载与校验脚本，不重新分发原始或转换后的数据。

## G1 功能词词典边界

G1 词典的版本是 `reddit_g1_function_words_en_v1`，包含 PDF 规定的八类：冠词、介词、人称代词、非人称代词、助动词、连词、常见副词和否定词。程序对规范化后的 `N1.tokens` 做精确匹配，不做词干或通配扩展；同一 token 若被明确列入多个类别，会在每个类别各计一次。

CDI 公式来自 Pennebaker 等人（2014）：

```text
CDI = 30 + article + preposition
         - personal_pronoun - impersonal_pronoun - auxiliary_verb
         - conjunction - adverb - negation
```

论文使用 LIWC 词类，但 LIWC 官方词典受单独许可证约束。因此仓库中的清单是依据公开公式和英语语法类别编写的透明项目资源，`liwc_compatible=false`，不得把数值描述为官方 LIWC 输出。理论来源：<https://doi.org/10.1371/journal.pone.0115844>。
