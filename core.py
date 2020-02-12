import re
import logging
from subword_nmt import apply_bpe
from sacremoses import MosesTokenizer, MosesDetokenizer
from utils import load_line_as_data

from joeynmt.helpers import load_config, get_latest_checkpoint, \
    load_checkpoint
from joeynmt.vocabulary import build_vocab
from joeynmt.model import build_model
from joeynmt.prediction import validate_on_data


def translate(message_text, model, src_vocab, trg_vocab, preprocess, postprocess,
              logger, beam_size, beam_alpha, level, lowercase,
              max_output_length, use_cuda):
    """
    Describes how to translate a text message.

    :param message_text: Slack command, could be text.
    :param model: The Joey NMT model.
    :param src_vocab: Source vocabulary.
    :param trg_vocab: Target vocabulary.
    :param preprocess: Preprocessing pipeline (a list).
    :param postprocess: Postprocessing pipeline (a list).
    :param beam_size: Beam size for decoding.
    :param beam_alpha: Beam alpha for decoding.
    :param level: Segmentation level.
    :param lowercase: Lowercasing.
    :param max_output_length: Maximum output length.
    :param use_cuda: Using CUDA or not.
    :return:
    """
    sentence = message_text.strip()
    # remove emojis
    emoji_pattern = re.compile("\:[a-zA-Z]+\:")
    sentence = re.sub(emoji_pattern, "", sentence)
    sentence = sentence.strip()
    if lowercase:
        sentence = sentence.lower()
    for p in preprocess:
        sentence = p(sentence)

    # load the data which consists only of this sentence
    test_data, src_vocab, trg_vocab = load_line_as_data(lowercase=lowercase,
        line=sentence, src_vocab=src_vocab, trg_vocab=trg_vocab, level=level)

    # generate outputs
    score, loss, ppl, sources, sources_raw, references, hypotheses, \
    hypotheses_raw, attention_scores = validate_on_data(
        model, data=test_data, batch_size=1, level=level,
        max_output_length=max_output_length, eval_metric=None,
        use_cuda=use_cuda, loss_function=None, beam_size=beam_size,
        beam_alpha=beam_alpha, logger=logger)

    # post-process
    if level == "char":
        response = "".join(hypotheses)
    else:
        response = " ".join(hypotheses)

    for p in postprocess:
        response = p(response)

    return response


def load_model(model_dir, bpe_src_code=None, tokenize=None):
    """
    Start the bot. This means loading the model according to the config file.

    :param model_dir: Model directory of trained Joey NMT model.
    :param bpe_src_code: BPE codes for source side processing (optional).
    :param tokenize: If True, tokenize inputs with Moses tokenizer.
    :return:
    """
    conf = {}
    cfg_file = model_dir+"/config.yaml"

    logger = logging.getLogger(__name__)
    conf["logger"] = logger
    # load the Joey configuration
    cfg = load_config(cfg_file)

    # load the checkpoint
    if "load_model" in cfg['training'].keys():
        ckpt = cfg['training']["load_model"]
    else:
        ckpt = get_latest_checkpoint(model_dir)
        if ckpt is None:
            raise FileNotFoundError("No checkpoint found in directory {}."
                                    .format(model_dir))

    # prediction parameters from config
    conf["use_cuda"] = cfg["training"].get("use_cuda", False)
    conf["level"] = cfg["data"]["level"]
    conf["max_output_length"] = cfg["training"].get("max_output_length", None)
    conf["lowercase"] = cfg["data"].get("lowercase", False)

    # load the vocabularies
    src_vocab_file = cfg["training"]["model_dir"] + "/src_vocab.txt"
    trg_vocab_file = cfg["training"]["model_dir"] + "/trg_vocab.txt"
    conf["src_vocab"] = build_vocab(field="src", vocab_file=src_vocab_file,
                            dataset=None, max_size=-1, min_freq=0)
    conf["trg_vocab"] = build_vocab(field="trg", vocab_file=trg_vocab_file,
                            dataset=None, max_size=-1, min_freq=0)

    # whether to use beam search for decoding, 0: greedy decoding
    if "testing" in cfg.keys():
        conf["beam_size"] = cfg["testing"].get("beam_size", 0)
        conf["beam_alpha"] = cfg["testing"].get("alpha", -1)
    else:
        conf["beam_size"] = 1
        conf["beam_alpha"] = -1

    # pre-processing
    if tokenize is not None:
        src_tokenizer = MosesTokenizer(lang=cfg["data"]["src"])
        trg_tokenizer = MosesDetokenizer(lang=cfg["data"]["trg"])
        # tokenize input
        tokenizer = lambda x: src_tokenizer.tokenize(x, return_str=True)
        detokenizer = lambda x: trg_tokenizer.detokenize(
            x.split(), return_str=True)
    else:
        tokenizer = lambda x: x
        detokenizer = lambda x: x

    if bpe_src_code is not None and level == "bpe":
        # load bpe merge file
        merge_file = open(bpe_src_code, "r")
        bpe = apply_bpe.BPE(codes=merge_file)
        segmenter = lambda x: bpe.process_line(x.strip())
    elif conf["level"] == "char":
        # split to chars
        segmenter = lambda x: list(x.strip())
    else:
        segmenter = lambda x: x.strip()

    conf["preprocess"] = [tokenizer, segmenter]
    conf["postprocess"] = [detokenizer]
    # build model and load parameters into it
    model_checkpoint = load_checkpoint(ckpt, conf["use_cuda"])
    model = build_model(cfg["model"], src_vocab=conf["src_vocab"], trg_vocab=conf["trg_vocab"])
    model.load_state_dict(model_checkpoint["model_state"])

    if conf["use_cuda"]:
        model.cuda()
    conf["model"] = model
    print("Joey NMT model loaded successfully.")
    return conf

