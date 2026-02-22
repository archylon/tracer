// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract GuerillaEngine is Ownable {
    
    interface IPulseXPair {
        function swap(uint amount0Out, uint amount1Out, address to, bytes calldata data) external;
        function token0() external view returns (address);
        function token1() external view returns (address);
    }

    constructor() Ownable(msg.sender) {}

    function pulseXCall(address sender, uint a0, uint a1, bytes calldata d) external { _logic(sender, d); }
    function uniswapV2Call(address sender, uint a0, uint a1, bytes calldata d) external { _logic(sender, d); }

    function _logic(address sender, bytes calldata data) internal {
        require(sender == address(this), "Unauthorized");

        (
            address pumpPool,
            bytes memory pumpData,
            address mintContract,
            bytes memory mintData,
            address dumpToken,   // The FED we just minted
            address dumpPool,    // The pool where we sell FED for TBILL
            bytes memory dumpData, // The encoded swap() call
            address repayToken,
            uint256 repayAmount
        ) = abi.decode(data, (address, bytes, address, bytes, address, address, bytes, address, uint256));

        // 1. THE PUMP
        if (pumpData.length > 0) {
            (bool s1, ) = pumpPool.call(pumpData);
            require(s1, "Pump failed");
        }

        // 2. THE MINT
        (bool s2, ) = mintContract.call(mintData);
        require(s2, "Mint failed");

        // 3. THE DUMP (Generic implementation)
        // We send ALL minted tokens to the dump pool first
        uint256 dumpBal = IERC20(dumpToken).balanceOf(address(this));
        if (dumpBal > 0 && dumpData.length > 0) {
            IERC20(dumpToken).transfer(dumpPool, dumpBal);
            (bool s3, ) = dumpPool.call(dumpData);
            require(s3, "Dump failed");
        }

        // 4. REPAYMENT
        IERC20(repayToken).transfer(msg.sender, repayAmount);

        // 5. PROFIT
        uint256 bal = IERC20(repayToken).balanceOf(address(this));
        if (bal > 0) IERC20(repayToken).transfer(owner(), bal);
    }

    function executeGuerilla(
        address flashPool,
        address tokenToBorrow,
        uint256 borrowAmount,
        bytes calldata missionBrief
    ) external onlyOwner {
        address t0 = IPulseXPair(flashPool).token0();
        uint256 a0 = (tokenToBorrow == t0) ? borrowAmount : 0;
        uint256 a1 = (a0 == 0) ? borrowAmount : 0;

        IPulseXPair(flashPool).swap(a0, a1, address(this), missionBrief);
    }

    function recoverToken(address t) external onlyOwner {
        IERC20(t).transfer(owner(), IERC20(t).balanceOf(address(this)));
    }
}