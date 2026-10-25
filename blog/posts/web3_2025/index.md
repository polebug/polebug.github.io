---
title: 分享 web3 入门计划｜2025 版
date: 2025-7-5 20:51 
desc: 
---
2022年，我刚进入 web3 行业的时候，在 [notion 上写过一版 web3 入门计划](https://cubic-leaf-731.notion.site/web3-202208-09-1623ccd15c2148a1ae00ed8794d153b1)。

前段时间，我惊奇的发现，还有很多人在看份入门计划，甚至最近收到了很多催更，问我现在想入门 web3 可以怎么学，和之前有什么不同。

<div style="display: flex; justify-content: center; align-items: center; margin: 30px 0;">
  <img src="Pasted Graphic.png" width="800" height="200" alt="web3 2022">
</div>

我最近刚好想整理一下这几年学习区块链的笔记，就顺便更新一版 web3 的入门计划，希望对想入行的大家有所帮助～

---

在分享之前，我想先提一下两个版本学习计划的背景。

2022 版的学习计划是写在我刚入行的时候，那时我还是个小白，对区块链所知甚少，所以给自己规划了六周时间去入门。后面觉得自己学的太浅了，非常不够用，陆续又花时间看了许多教程和 paper。

第一版的学习强度我觉得不太足够，顶多是算了解了一遍，还没到入门的水平。并且，我当时是一边学一边做的总结，这就导致学习列表里的质量是参差不齐的。因为我当时前提找资料的时候，也不知道它到底质量如何，所以第一版的旁边有一个推荐指数，和我的评价（没到90分基本都是不推荐的）。

那这次 2025 版的学习计划，我会给出丰富且全面的学习材料，学习的时间也会更长，大家可以按自己的节奏和侧重点去学。

---

#### Part0. 整体的学习思路

从学习的框架上来说，第一版和第二版其实没有太大的变化，还是从链到各个赛道去学习。

<div style="display: flex; justify-content: center; align-items: center; margin: 30px 0;">
  <img src="0_D8929USL2WWWNOZF.png" width="800" height="160" alt="web3 2022">
</div>

可以参考 coinbase web3 stack 这张图，虽然它是 2022 年的，但是三年过去了，好像也没有发生什么变化 😅 现在仍然可以从 Protocol Layer 到 DApp 去入门。

---

#### Part1. 区块链的基础知识

学习 web3 的第一步，需要了解一些区块链基础的概念和学习 Protocol Layer 的底层原理。

<style>
  table.simple-bordered {
    border-collapse: collapse;
    width: 100%;
    font-family: Arial, sans-serif;
	font-size: 15px;
	margin-top: 10px;
	margin-bottom: 10px;
  }

  table.simple-bordered th,
  table.simple-bordered td {
    border: 1px solid #999;
    padding: 10px;
    text-align: left;
	vertical-align: top;
    background-color: transparent;
  }

  table.simple-bordered ul {
    margin: 0;
    padding-left: 16px; /* 调小缩进 */
  }

  table.simple-bordered th {
    font-weight: bold;
  }

  table.simple-bordered a {
    text-decoration: none;
  }

  table.simple-bordered a:hover {
    text-decoration: underline;
  }
</style>

<table class="simple-bordered">
  <thead>
    <tr>
      <th>学习目标</th>
      <th>材料</th>
      <th>补充</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        1. 理解密码学在区块链中的核心作用； <br>
        2. 掌握区块链的基本概念； <br>
        3. 构建对金融系统及加密金融逻辑的基础理解；
      </td>
      <td>
        <ul>
          <li>
            <a href="https://ocw.mit.edu/courses/sloan-school-of-management/15-s12-blockchain-and-money-fall-2018/" target="_blank">
              MIT Blockchain and Money (15.S12)
            </a><br>
            MIT 这个课很适合入门去听，可以只看 Session1–6：<br> 包括传统金融、区块链技术、相关加密算法、智能合约和 DAPP 的概念；
          </li>
        </ul>
      </td>
      <td></td>
    </tr>
    <tr>
      <td>
        掌握主流公链：<br>
        1. Bitcoin <br>
        2. Ethereum <br>
        3. Solana <br>
        底层原理及其差异
      </td>
      <td>
        <ul>
          <li><a href="https://bitcoin.org/bitcoin.pdf" target="_blank">Bitcoin whitepaper</a></li>
          <li><a href="https://ethereum.org/en/whitepaper/" target="_blank">Ethereum whitepaper</a></li>
          <li><a href="https://solana.com/solana-whitepaper.pdf" target="_blank">Solana whitepaper</a></li>
        </ul>
      </td>
      <td>
        <ul>
          <li>
            推荐肖臻老师的 <strong>北大区块链公开课</strong>：<br> 仔细读白皮书能懂个大概的意思，但如果想要加深理解，我非常推荐去看肖臻老师的课。<br>
			这个课讲得很详细（关于挖矿、分叉等各种细节都有讲到），但需要看挺久的，20h+；
          </li>
          <li>
            Vitalik 关于 <a href="https://vitalik.eth.limo/general/2017/12/31/pos_faq.html#what-is-proof-of-stake" target="_blank">Proof of Stake 的文章</a>
          </li>
          <li>
            <a href="https://docs.anza.xyz/clusters" target="_blank">Solana 官方文档</a> 也可以看看
          </li>
        </ul>
      </td>
    </tr>
  </tbody>
</table>

---

#### Part2. 初步了解智能合约的概念和执行环境

当我们建立了对区块链的宏观认知底层原理之后，我们来到了更上一层——智能合约，但是别急着学习智能合约的开发，你需要先了解智能合约的基本定义、运行方式、特性等等，对智能合约的底层运行机制有基本认识，后续如果有兴趣，再开始动手学习智能合约的开发部分。

<table class="simple-bordered">
  <thead>
    <tr>
      <th>学习目标</th>
      <th>材料</th>
      <th>补充</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>了解智能合约的定义与特性</td>
      <td>
        <ul>
          <li><a href="https://ethereum.org/en/developers/docs/smart-contracts/" target="_blank">Ethereum 官方文档关于智能合约的介绍</a></li>
          <li><a href="https://ethereum.org/en/developers/docs/gas/" target="_blank">关于 Gas 和 Fee 的介绍</a></li>
          <li><a href="https://solana.com/docs/core" target="_blank">Solana Core Concepts</a></li>
        </ul>
      </td>
      <td>
        <ul>
          <li><strong>《Mastering Ethereum》</strong> <a href="https://github.com/ethereumbook/ethereumbook/blob/develop/07smart-contracts-solidity.asciidoc" target="_blank">关于智能合约的部分（第 7–10 章）</a></li>
        </ul>
      </td>
    </tr>
    <tr>
      <td>了解智能合约的执行环境</td>
      <td>
        <a href="https://ethereum.org/en/developers/docs/evm/" target="_blank">Ethereum 官方文档关于 EVM 的介绍</a>
      </td>
      <td>
        感兴趣的朋友也可以了解其他虚拟机环境，例如 
        <a href="https://docs.substrate.io/" target="_blank">WASM</a>
      </td>
    </tr>
  </tbody>
</table>

时间充裕的情况，可以把 Ethereum 的官方文档都翻一遍，很多文档都是概念和定义。

---

#### Part3. 了解各个赛道的 DApp 和其背后的设计

了解完区块链和智能合约之后，我们就已经算是把相关的概念都学完了。

接下来我们应该去学习区块链上的具体应用场景（DApp），可以从不同赛道中挑选有代表性的项目，通过阅读官方文档和白皮书学习这些 DApp 的设计。

<table class="simple-bordered">
  <thead>
    <tr>
      <th>学习目标</th>
      <th>材料</th>
      <th>补充</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>理解 DApp 的主要设计（链+合约+钱包+前端）</td>
      <td>
        <ul>
          <li>
            <a href="https://ethereum.org/en/developers/docs/dapps/" target="_blank">
              以太坊官方文档关于 DApp 架构的介绍
            </a>
          </li>
          <li>
            <a href="https://ethereum.org/en/developers/docs/web2-vs-web3/" target="_blank">
              关于 web2 和 web3 的区别
            </a>
          </li>
        </ul>
      </td>
      <td></td>
    </tr>
    <tr>
      <td>了解 DeFi</td>
      <td>
        <ul>
          <li><a href="https://github.com/Uniswap/v2-core" target="_blank">Uniswap v2 core</a></li>
          <li>
            <a href="https://uniswap.org/whitepaper-v3.pdf" target="_blank">Uniswap v3 白皮书</a> 
          </li>
          <li><a href="https://docs.aave.com/" target="_blank">AAVE 协议的官方文档</a></li>
        </ul>
      </td>
      <td>
        DeFi 值得学习的项目有很多，还可以<br>看看
        Raydium、Curve、Compound，<br>
        感兴趣的朋友自行找找官方文档即可；
      </td>
    </tr>
    <tr>
      <td>了解 NFT</td>
      <td>
        <ul>
          <li>
            <a href="https://eips.ethereum.org/EIPS/eip-721" target="_blank">关于 ERC-721 标准</a>
          </li>
          <li>
            <a href="https://eips.ethereum.org/EIPS/eip-1155" target="_blank">关于 ERC-1155 标准</a>
          </li>
        </ul>
      </td>
      <td></td>
    </tr>
    <tr>
      <td>了解 GameFi</td>
      <td>
	  <ul>
        <li><a href="https://whitepaper.axieinfinity.com/" target="_blank">经典项目：Axie</a></li></ul>
      </td>
      <td>
        GameFi、SocialFi 的设计都比较简单，<br>
        基本上是 NFT + 链的设计，这俩赛道就随便看看；
      </td>
    </tr>
    <tr>
      <td>了解 SocialFi</td>
      <td>
        <ul>
          <li>
            <a href="https://docs.farcaster.xyz/" target="_blank">Farcaster Protocol 文档</a>
          </li>
          <li>
            <a href="https://docs.lens.xyz/docs/intro" target="_blank">Lens Protocol 文档</a>
          </li>
        </ul>
      </td>
      <td></td>
    </tr>
    <tr>
      <td>了解 Layer2</td>
      <td>
        <ul>
          <li><a href="https://docs.optimism.io/" target="_blank">Optimism</a></li>
          <li><a href="https://developer.arbitrum.io/" target="_blank">Arbitrum</a></li>
        </ul>
      </td>
      <td>
        Layer2 太多了，还有 Scroll、Linea、<br>
		zkSync，挑几个喜欢的了解了解即可；
      </td>
    </tr>
  </tbody>
</table>

---

#### Part4: 入门 DApp 的开发

最后是实践环节，可以尝试写一个 DApp，如果你并不想学习智能合约的开发，也可以钱包交互+前端，或者是链上合约的数据解析+后端。

因为本人是后端+智能合约的技术栈，下面推荐的学习材料也是围绕这两方面。

<table class="simple-bordered">
  <thead>
    <tr>
      <th>学习目标</th>
      <th>材料</th>
      <th>补充</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1. 入门智能合约的基本语法、框架；<br>2. 用智能合约写一个简单的 DApp；</td>
      <td>
        <ul>
          <li>Solidity 教程 <a href="https://solidity-by-example.org/hello-world/" target="_blank">Solidity By Example</a></li>
          <li>Solidity By Example 也有相关的 <a href="https://www.youtube.com/playlist?list=PLvrAcVH0nwP-eMuKoR4rBd6Mz7z8lvh8i" target="_blank">视频教程</a> 可以跟着学</li>
          <li><a href="https://github.com/trufflesuite/truffle" target="_blank">Truffle 框架</a></li>
          <li><a href="https://github.com/eth-brownie/brownie" target="_blank">Brownie 框架</a></li>
          <li><a href="https://github.com/NomicFoundation/hardhat" target="_blank">Hardhat 框架</a></li>
          <li><a href="https://www.anchor-lang.com/docs" target="_blank">Solana Anchor 官方教程</a></li>
          <li>Anchor 的视频教程我看的是 <a href="https://www.youtube.com/playlist?list=PL53JxaGwWUqCr3xm4qvqbgpJ4Xbs4lCs7" target="_blank">Josh 大佬的视频</a>，觉得他讲的特别好</li>
        </ul>
      </td>
      <td>不一定要全部学完，可以自己定一个想要实现的效果，带着目标去学；</td>
    </tr>
    <tr>
      <td>学习智能合约相关的工具</td>
      <td>
        <ul>
          <li><a href="https://remix.ethereum.org/" target="_blank">Remix IDE</a></li>
          <li><a href="https://www.openzeppelin.com" target="_blank">OpenZeppelin</a></li>
          <li>Solana 智能合约的 <a href="https://solana.com/docs/programs/deploying#bpf-programs" target="_blank">部署文档</a></li>
        </ul>
      </td>
      <td></td>
    </tr>
    <tr>
      <td>学习web3相关的后端技术：<ul><li> 与智能合约交互</li><li> 解析链上数据 transaction/event</li></ul></td>
      <td>
        <ul>
          <li><a href="https://goethereumbook.org/en/" target="_blank">Ethereum Development with Go</a> 的教程基本够用</li>
        </ul>
      </td>
      <td></td>
    </tr>
  </tbody>
</table>

---

如果你每天学习 1.5-2h，part1-3 我预计需要学习 5 周（不算补充材料的学习），它们大多数都在看各种文档，并不需要花太多时间。

为什么比第一版时间短呢，因为第一版里有许多低质量的教程浪费了些时间，第二版都规避了。

以上！希望大家学的开心！

> 声明：此篇文章版权属于 polebug 所有。其他媒体、网站或个人转载使用时不得进行商业性的原版原式的转载，也不得歪曲和篡改本网站所发布的内容。

