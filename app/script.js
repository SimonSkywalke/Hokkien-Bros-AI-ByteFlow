// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化赛博朋克特效
    initCyberpunkEffects();
    console.log('ByteFlow 页面已加载，开始初始化数字海浪特效...');
});

// 赛博朋克特效初始化
function initCyberpunkEffects() {
    console.log('初始化赛博朋克特效...');
    setTimeout(() => {
        initDigitalGrid();
        initButtonEffects();
    }, 100);
}

// 初始化数字网格海浪
function initDigitalGrid() {
    const waveGrid = document.getElementById('waveGrid');
    if (!waveGrid) {
        console.error('找不到数字网格容器！');
        return;
    }
    
    const cellSize = 15;
    const cols = Math.floor(window.innerWidth / cellSize);
    const rows = Math.floor(window.innerHeight / cellSize);
    
    waveGrid.style.gridTemplateColumns = `repeat(${cols}, ${cellSize}px)`;
    waveGrid.style.gridTemplateRows = `repeat(${rows}, ${cellSize}px)`;
    waveGrid.style.gap = '1px';
    
    const cells = [];
    for (let row = 0; row < rows; row++) {
        cells[row] = [];
        for (let col = 0; col < cols; col++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            waveGrid.appendChild(cell);
            cells[row][col] = cell;
        }
    }
    
    console.log(`创建了 ${rows}x${cols} 的网格`);
    startNaturalWaveAnimation(cells, rows, cols);
}

// 自然海浪动画控制
function startNaturalWaveAnimation(cells, rows, cols) {
    function createNaturalWave() {
        const waveOriginX = Math.random() * cols;
        const waveOriginY = -10;
        const waveSpeed = 0.3 + Math.random() * 0.4;
        const waveWidth = 8 + Math.random() * 15;
        const waveHeight = 15 + Math.random() * 20;
        const turbulence = 2 + Math.random() * 3;
        
        let currentY = waveOriginY;
        
        function animateWaveStep() {
            currentY += waveSpeed;
            
            if (currentY > rows + waveHeight) {
                return;
            }
            
            for (let deltaY = 0; deltaY < waveHeight; deltaY++) {
                const row = Math.floor(currentY - deltaY);
                if (row < 0 || row >= rows) continue;
                
                const waveIntensity = Math.sin((deltaY / waveHeight) * Math.PI);
                const currentWaveWidth = waveWidth * waveIntensity;
                const turbulenceOffset = Math.sin(currentY * 0.1) * turbulence + Math.cos(currentY * 0.15) * turbulence * 0.5;
                const centerX = waveOriginX + turbulenceOffset;
                
                for (let deltaX = -currentWaveWidth/2; deltaX <= currentWaveWidth/2; deltaX++) {
                    const col = Math.floor(centerX + deltaX);
                    if (col < 0 || col >= cols) continue;
                    
                    const distanceFromCenter = Math.abs(deltaX) / (currentWaveWidth/2);
                    const intensity = (1 - distanceFromCenter) * waveIntensity;
                    
                    if (cells[row] && cells[row][col] && intensity > 0.3) {
                        const cell = cells[row][col];
                        const activationDelay = Math.random() * 100;
                        
                        setTimeout(() => {
                            if (intensity > 0.8) {
                                cell.classList.add('wave-active');
                                
                                if (Math.random() > 0.6) {
                                    const digit = Math.random() > 0.5 ? '1' : '0';
                                    cell.textContent = digit;
                                    cell.style.color = '#00ff88';
                                    cell.style.fontSize = '10px';
                                    cell.style.textAlign = 'center';
                                    cell.style.lineHeight = '15px';
                                    cell.style.fontFamily = 'Courier New, monospace';
                                    cell.style.fontWeight = 'bold';
                                }
                                
                                setTimeout(() => {
                                    cell.classList.remove('wave-active');
                                    cell.classList.add('wave-fade');
                                    
                                    setTimeout(() => {
                                        cell.classList.remove('wave-fade');
                                        cell.classList.add('wave-weak');
                                        
                                        setTimeout(() => {
                                            cell.classList.remove('wave-weak');
                                            cell.textContent = '';
                                        }, 2000);
                                    }, 1200);
                                }, 800);
                                
                            } else if (intensity > 0.5) {
                                cell.classList.add('wave-fade');
                                setTimeout(() => {
                                    cell.classList.remove('wave-fade');
                                    cell.classList.add('wave-weak');
                                    setTimeout(() => {
                                        cell.classList.remove('wave-weak');
                                    }, 1500);
                                }, 600);
                            } else {
                                cell.classList.add('wave-weak');
                                setTimeout(() => {
                                    cell.classList.remove('wave-weak');
                                }, 800);
                            }
                        }, activationDelay);
                    }
                }
            }
            
            requestAnimationFrame(animateWaveStep);
        }
        
        animateWaveStep();
    }
    
    function continuousWaves() {
        createNaturalWave();
        const nextWaveDelay = Math.random() * 3000 + 2000;
        setTimeout(continuousWaves, nextWaveDelay);
    }
    
    continuousWaves();
    console.log('自然海浪动画已启动');
}

// 按钮交互效果
function initButtonEffects() {
    const startButton = document.querySelector('.start-button');
    if (startButton) {
        startButton.addEventListener('click', function() {
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
            console.log('开始使用 ByteFlow!');
        });
    }
}

// 窗口大小改变时重新初始化网格
window.addEventListener('resize', function() {
    setTimeout(() => {
        const waveGrid = document.getElementById('waveGrid');
        if (waveGrid) {
            waveGrid.innerHTML = '';
            initDigitalGrid();
        }
    }, 100);
});

// 数字计数动画
function animateValue(element, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const current = Math.floor(progress * (end - start) + start);
        element.innerHTML = current + (element.dataset.suffix || '');
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

// 当统计数字进入视口时开始动画
const statsObserver = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const statNumber = entry.target.querySelector('.stat-number');
            if (statNumber && !statNumber.classList.contains('animated')) {
                statNumber.classList.add('animated');
                const text = statNumber.textContent;
                const number = parseInt(text.replace(/\D/g, ''));
                const suffix = text.replace(/\d/g, '');
                statNumber.dataset.suffix = suffix;
                
                // 添加点击涟漪效果
                statNumber.addEventListener('click', function(e) {
                    createNumberRipple(this, e);
                });
                
                // 添加鼠标悬停时的涟漪效果
                statNumber.addEventListener('mouseenter', function() {
                    this.classList.add('ripple');
                    setTimeout(() => {
                        this.classList.remove('ripple');
                    }, 600);
                });
                
                animateValue(statNumber, 0, number, 2000);
            }
        }
    });
});

// 创建数字涟漪效果
function createNumberRipple(element, event) {
    const rect = element.getBoundingClientRect();
    const ripple = document.createElement('div');
    const size = Math.max(rect.width, rect.height) * 2;
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;
    
    ripple.style.cssText = `
        position: absolute;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(0, 255, 136, 0.6) 0%, rgba(0, 204, 102, 0.4) 50%, transparent 70%);
        transform: translate(-50%, -50%) scale(0);
        animation: rippleEffect 0.8s ease-out;
        left: ${x}px;
        top: ${y}px;
        width: ${size}px;
        height: ${size}px;
        pointer-events: none;
        z-index: 10;
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.4);
    `;
    
    element.style.position = 'relative';
    element.style.overflow = 'hidden';
    element.appendChild(ripple);
    
    // 移除涟漪效果
    setTimeout(() => {
        ripple.remove();
    }, 800);
    
    // 重新播放数字动画
    const originalText = element.textContent;
    const number = parseInt(originalText.replace(/\D/g, ''));
    animateValue(element, 0, number, 1000);
}

document.querySelectorAll('.stat').forEach(stat => {
    statsObserver.observe(stat);
});

// 代码打字效果
function typeWriter(element, text, speed = 50) {
    let i = 0;
    element.innerHTML = '';
    
    function type() {
        if (i < text.length) {
            element.innerHTML += text.charAt(i);
            i++;
            setTimeout(type, speed);
        }
    }
    
    type();
}

// 当代码预览进入视口时开始打字效果
const codeObserver = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const codeLines = entry.target.querySelectorAll('.code-line');
            if (codeLines.length > 0 && !entry.target.classList.contains('typed')) {
                entry.target.classList.add('typed');
                
                codeLines.forEach((line, index) => {
                    const originalText = line.innerHTML;
                    setTimeout(() => {
                        typeWriter(line, originalText, 30);
                    }, index * 800);
                });
            }
        }
    });
});

const codePreview = document.querySelector('.code-preview');
if (codePreview) {
    codeObserver.observe(codePreview);
}

// 响应式菜单样式
const mobileMenuStyle = document.createElement('style');
mobileMenuStyle.textContent = `
    @media (max-width: 768px) {
        .nav-menu.active {
            display: flex;
            position: absolute;
            top: 100%;
            left: 0;
            width: 100%;
            background: rgba(10, 10, 10, 0.98);
            flex-direction: column;
            padding: 20px;
            gap: 1rem;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .hamburger.active .bar:nth-child(2) {
            opacity: 0;
        }
        
        .hamburger.active .bar:nth-child(1) {
            transform: translateY(8px) rotate(45deg);
        }
        
        .hamburger.active .bar:nth-child(3) {
            transform: translateY(-8px) rotate(-45deg);
        }
    }
`;
document.head.appendChild(mobileMenuStyle);

// 赛博朋克特效初始化
function initCyberpunkEffects() {
    console.log('初始化赛博朋克特效...');
    
    // 确保只在主页初始化背景特效
    if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
        setTimeout(() => {
            initDigitalGrid();
            initButtonEffects();
        }, 100);
    } else {
        // 非主页只初始化按钮特效
        setTimeout(() => {
            initButtonEffects();
        }, 100);
    }
}

// 按钮交互效果
function initButtonEffects() {
    const startButton = document.querySelector('.start-button');
    if (startButton) {
        startButton.addEventListener('click', function() {
            // 点击效果
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
            
            // 这里可以添加实际的功能逻辑
            console.log('开始使用 ByteFlow!');
        });
    }
}

// 初始化数字网格海浪
function initDigitalGrid() {
    const waveGrid = document.getElementById('waveGrid');
    console.log('数字网格容器:', waveGrid);
    
    if (!waveGrid) {
        console.error('找不到数字网格容器！');
        return;
    }
    
    // 计算网格尺寸
    const cellSize = 15;
    const cols = Math.floor(window.innerWidth / cellSize);
    const rows = Math.floor(window.innerHeight / cellSize);
    
    // 设置网格样式
    waveGrid.style.gridTemplateColumns = `repeat(${cols}, ${cellSize}px)`;
    waveGrid.style.gridTemplateRows = `repeat(${rows}, ${cellSize}px)`;
    waveGrid.style.gap = '1px';
    
    // 创建网格单元格
    const cells = [];
    for (let row = 0; row < rows; row++) {
        cells[row] = [];
        for (let col = 0; col < cols; col++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            cell.dataset.row = row;
            cell.dataset.col = col;
            waveGrid.appendChild(cell);
            cells[row][col] = cell;
        }
    }
    
    console.log(`创建了 ${rows}x${cols} 的网格`);
    
    // 启动自然海浪效果
    startNaturalWaveAnimation(cells, rows, cols);
}

// 自然海浪动画控制
function startNaturalWaveAnimation(cells, rows, cols) {
    
    function createNaturalWave() {
        // 随机生成海浪起点和参数
        const waveOriginX = Math.random() * cols;
        const waveOriginY = -15; // 从屏幕上方开始
        const waveSpeed = 0.8 + Math.random() * 0.8; // 增加速度变化
        const waveWidth = 20 + Math.random() * 30; // 增加宽度变化
        const waveHeight = 25 + Math.random() * 35; // 增加高度变化
        const turbulence = 8 + Math.random() * 12; // 增强湍流
        const frequency = 0.08 + Math.random() * 0.04; // 波浪频率
        
        let currentY = waveOriginY;
        let timeOffset = 0;
        
        function animateWaveStep() {
            currentY += waveSpeed;
            timeOffset += 0.1;
            
            // 海浪已经离开屏幕时停止
            if (currentY > rows + waveHeight) {
                return;
            }
            
            // 为当前海浪位置的每一行激活方块
            for (let deltaY = 0; deltaY < waveHeight; deltaY++) {
                const row = Math.floor(currentY - deltaY);
                if (row < 0 || row >= rows) continue;
                
                // 使用多重正弦函数创建更自然的海浪形状
                const primaryWave = Math.sin((deltaY / waveHeight) * Math.PI);
                const secondaryWave = Math.sin((deltaY / waveHeight) * Math.PI * 2) * 0.3;
                const waveIntensity = Math.max(0, primaryWave + secondaryWave);
                
                const currentWaveWidth = waveWidth * waveIntensity;
                
                // 增强湍流效果，模拟真实海浪的不规则性
                const time = currentY * frequency + timeOffset;
                const turbulenceX = Math.sin(time) * turbulence + 
                                   Math.cos(time * 1.3) * turbulence * 0.6 +
                                   Math.sin(time * 0.7) * turbulence * 0.4;
                
                const turbulenceY = Math.sin(time * 1.1) * 2 + Math.cos(time * 0.9) * 1.5;
                
                const centerX = waveOriginX + turbulenceX;
                const effectiveRow = row + Math.floor(turbulenceY);
                
                if (effectiveRow < 0 || effectiveRow >= rows) continue;
                
                for (let deltaX = -currentWaveWidth/2; deltaX <= currentWaveWidth/2; deltaX++) {
                    const col = Math.floor(centerX + deltaX);
                    if (col < 0 || col >= cols) continue;
                    
                    // 计算方块在海浪中的强度，添加径向衰减
                    const distanceFromCenter = Math.abs(deltaX) / (currentWaveWidth/2);
                    const radialFade = Math.cos(distanceFromCenter * Math.PI / 2);
                    const intensity = waveIntensity * radialFade;
                    
                    // 添加随机抖动，模拟水花效果
                    const jitter = (Math.random() - 0.5) * 0.3;
                    const finalIntensity = Math.max(0, intensity + jitter);
                    
                    if (cells[effectiveRow] && cells[effectiveRow][col] && finalIntensity > 0.2) {
                        const cell = cells[effectiveRow][col];
                        
                        // 根据强度设置不同级别的激活
                        const activationDelay = Math.random() * 200;
                        
                        setTimeout(() => {
                            if (finalIntensity > 0.75) {
                                // 高强度激活 - 浪峰
                                cell.classList.add('wave-active');
                                
                                // 随机显示数字流
                                if (Math.random() > 0.5) {
                                    const digits = ['0', '1', '0', '1', '1', '0'];
                                    const digit = digits[Math.floor(Math.random() * digits.length)];
                                    cell.textContent = digit;
                                    cell.style.color = '#00ff88';
                                    cell.style.fontSize = '10px';
                                    cell.style.textAlign = 'center';
                                    cell.style.lineHeight = '15px';
                                    cell.style.fontFamily = 'Courier New, monospace';
                                    cell.style.fontWeight = 'bold';
                                    cell.style.textShadow = '0 0 5px rgba(0, 255, 136, 0.8)';
                                }
                                
                                setTimeout(() => {
                                    cell.classList.remove('wave-active');
                                    cell.classList.add('wave-fade');
                                    
                                    setTimeout(() => {
                                        cell.classList.remove('wave-fade');
                                        cell.classList.add('wave-weak');
                                        
                                        setTimeout(() => {
                                            cell.classList.remove('wave-weak');
                                            cell.textContent = '';
                                        }, 3000);
                                    }, 1500);
                                }, 1000);
                                
                            } else if (finalIntensity > 0.5) {
                                // 中强度激活 - 浪体
                                cell.classList.add('wave-fade');
                                
                                setTimeout(() => {
                                    cell.classList.remove('wave-fade');
                                    cell.classList.add('wave-weak');
                                    
                                    setTimeout(() => {
                                        cell.classList.remove('wave-weak');
                                    }, 2000);
                                }, 800);
                            } else if (finalIntensity > 0.3) {
                                // 低强度激活 - 浪尾
                                cell.classList.add('wave-weak');
                                
                                setTimeout(() => {
                                    cell.classList.remove('wave-weak');
                                }, 1200);
                            } else {
                                // 微弱激活 - 水花
                                cell.style.opacity = '0.3';
                                cell.style.background = 'rgba(0, 255, 136, 0.1)';
                                
                                setTimeout(() => {
                                    cell.style.opacity = '';
                                    cell.style.background = '';
                                }, 600);
                            }
                        }, activationDelay);
                    }
                }
            }
            
            // 继续下一帧
            requestAnimationFrame(animateWaveStep);
        }
        
        animateWaveStep();
    }
    
    // 持续创建海浪
    function continuousWaves() {
        createNaturalWave();
        
        // 随机间隔创建下一个海浪，模拟真实海浪的不规律性
        const nextWaveDelay = Math.random() * 2000 + 1500; // 1.5-3.5秒间隔
        setTimeout(continuousWaves, nextWaveDelay);
    }
    
    // 启动持续海浪
    continuousWaves();
    
    console.log('增强版自然海浪动画已启动');
}

// 窗口大小改变时重新初始化网格
window.addEventListener('resize', function() {
    setTimeout(() => {
        const waveGrid = document.getElementById('waveGrid');
        if (waveGrid) {
            waveGrid.innerHTML = ''; // 清空网格
            initDigitalGrid(); // 重新初始化
        }
    }, 100);
});

// 初始化所有增强效果
function initEnhancedEffects() {
    // 为按钮添加动态渐变效果
    const buttons = document.querySelectorAll('.btn-primary');
    buttons.forEach(button => {
        button.style.background = 'linear-gradient(135deg, #00ff88 0%, #00cc66 25%, #009944 50%, #00cc66 75%, #00ff88 100%)';
        button.style.backgroundSize = '300% 300%';
        button.style.animation = 'gradientShift 3s ease-in-out infinite';
        
        button.addEventListener('mouseenter', function() {
            this.style.animationDuration = '1s';
        });
        
        button.addEventListener('mouseleave', function() {
            this.style.animationDuration = '3s';
        });
    });
    
    // 为特色卡片添加动态边框
    const featureCards = document.querySelectorAll('.feature-card');
    featureCards.forEach(card => {
        card.style.border = '1px solid transparent';
        card.style.background = 'linear-gradient(rgba(0, 0, 0, 0.8), rgba(26, 26, 26, 0.8)) padding-box, linear-gradient(135deg, #00ff88, #00cc66, #009944) border-box';
        
        card.addEventListener('mouseenter', function() {
            this.style.background = 'linear-gradient(rgba(0, 0, 0, 0.9), rgba(26, 26, 26, 0.9)) padding-box, linear-gradient(135deg, #009944, #00ff88, #00cc66) border-box';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.background = 'linear-gradient(rgba(0, 0, 0, 0.8), rgba(26, 26, 26, 0.8)) padding-box, linear-gradient(135deg, #00ff88, #00cc66, #009944) border-box';
        });
    });
}

// 添加数字计数动画
    
